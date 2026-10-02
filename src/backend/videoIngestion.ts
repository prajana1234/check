import { findDemoVideoByName } from "@/mock/demoVideos";
import type { ProcessedDetection } from "./trafficProcessor";
import { TrafficProcessor } from "./trafficProcessor";
import { trafficStore } from "./trafficStore";
import { findFirebaseProcessed, fingerprintVideo, persistFirebaseProcessed } from "./firebaseTraffic";
import { getFirebaseClient } from "./firebaseClient";
import { analyzeUploadedVideo, type VisionIncidentEvent } from "@/services/visionService";
import type { Severity, ViolationType } from "@/types";

function videoIdFromName(name: string): string {
  return name.replace(/\.[^.]+$/, "").trim().replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_+|_+$/g, "").toUpperCase();
}

function timestampInSeconds(timestamp: string): number {
  const parts = timestamp.split(":").map(Number);
  return parts.length === 2 ? parts[0] * 60 + parts[1] : parts[0] * 3600 + parts[1] * 60 + parts[2];
}

function captureFrame(file: File, timestamp: string): Promise<string | undefined> {
  return new Promise((resolve, reject) => {
    const video = document.createElement("video");
    const url = URL.createObjectURL(file);
    const timeout = window.setTimeout(() => finish(undefined, new Error(`Timed out capturing evidence at ${timestamp}.`)), 8000);
    let settled = false;
    let candidates: number[] = [];
    let candidateIndex = 0;

    function finish(value: string | undefined, error?: Error) {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      URL.revokeObjectURL(url);
      if (error) reject(error);
      else resolve(value);
    }

    function seekNextFrame() {
      if (candidateIndex >= candidates.length) {
        finish(undefined, new Error("Could not find a visible frame to use as evidence."));
        return;
      }
      video.currentTime = candidates[candidateIndex++];
    }

    video.preload = "metadata";
    video.muted = true;
    video.onloadedmetadata = () => {
      if (!Number.isFinite(video.duration) || video.duration <= 0) {
        finish(undefined, new Error("The video has no readable frames."));
        return;
      }
      const lastFrameTime = Math.max(0, video.duration - 0.05);
      const target = timestampInSeconds(timestamp);
      candidates = [target, target + 0.5, target - 0.5, target + 1, target - 1, video.duration / 2, 1, lastFrameTime]
        .map((seconds) => Math.min(lastFrameTime, Math.max(0, seconds)))
        .map((seconds) => seconds === 0 && lastFrameTime > 0 ? Math.min(0.05, lastFrameTime) : seconds)
        .filter((seconds, index, values) => values.findIndex((value) => Math.abs(value - seconds) < 0.01) === index);
      seekNextFrame();
    };
    video.onseeked = () => {
      window.requestAnimationFrame(() => {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const context = canvas.getContext("2d");
        if (!context || canvas.width === 0 || canvas.height === 0) {
          finish(undefined, new Error("The video frame could not be rendered."));
          return;
        }
        try {
          context.drawImage(video, 0, 0, canvas.width, canvas.height);
          const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
          const sampleStride = Math.max(4, Math.floor((pixels.length / 4) / 1024) * 4);
          let visiblePixels = 0;
          for (let index = 0; index < pixels.length; index += sampleStride) {
            if (pixels[index] + pixels[index + 1] + pixels[index + 2] > 36 && ++visiblePixels >= 4) break;
          }
          if (visiblePixels < 4) {
            seekNextFrame();
            return;
          }
          finish(canvas.toDataURL("image/jpeg", 0.9));
        } catch {
          finish(undefined, new Error("The video frame could not be rendered."));
        }
      });
    };
    video.onerror = () => {
      finish(undefined, new Error(`Unable to capture evidence frame at ${timestamp}.`));
    };
    video.src = url;
  });
}

function isBlankEvidencePreview(preview: string | undefined): Promise<boolean> {
  if (!preview) return Promise.resolve(true);
  if (!preview.startsWith("data:image/")) return Promise.resolve(false);
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext("2d");
      if (!context || canvas.width === 0 || canvas.height === 0) {
        resolve(true);
        return;
      }
      context.drawImage(image, 0, 0);
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
      const stride = Math.max(4, Math.floor((pixels.length / 4) / 1024) * 4);
      let visiblePixels = 0;
      for (let index = 0; index < pixels.length; index += stride) {
        if (pixels[index] + pixels[index + 1] + pixels[index + 2] > 36 && ++visiblePixels >= 4) break;
      }
      resolve(visiblePixels < 4);
    };
    image.onerror = () => resolve(true);
    image.src = preview;
  });
}

export type VideoIngestionOptions = { cameraId?: string; location?: string };

function severityForEvent(event: VisionIncidentEvent): Severity {
  if (event.severity) return event.severity;
  if (event.violation === "Signal Jumping") return "critical";
  if (event.violation === "Wrong Lane" || event.violation === "Triple Riding") return "high";
  return "medium";
}

async function ingestWithInference(
  file: File,
  videoId: string,
  options: VideoIngestionOptions,
): Promise<{ processed?: ProcessedDetection; processedList: ProcessedDetection[]; duplicate: false }> {
  const cameraId = options.cameraId ?? "CAM-001";
  const location = options.location?.trim() || "Uploaded video";
  const analysis = await analyzeUploadedVideo(file, cameraId);
  await trafficStore.hydrate();

  const uploadedAt = new Date().toISOString();
  const firebaseEnabled = Boolean(getFirebaseClient());
  const fingerprint = firebaseEnabled ? await fingerprintVideo(file) : undefined;
  const processedList: ProcessedDetection[] = [];

  for (const [index, event] of analysis.incidents.entries()) {
    const sequence = trafficStore.nextSequenceNumbers();
    let processed = new TrafficProcessor(sequence.incident - 1, sequence.evidence - 1).process(
      {
        videoId,
        violation: event.violation as ViolationType,
        timestamp: event.timestamp,
        cameraId: event.camera_id || cameraId,
        severity: severityForEvent(event),
        vehicleId: event.vehicle_id || "UNKNOWN",
        licensePlate: event.license_plate || "UNKNOWN",
        speed: event.speed_kmh,
        speedLimit: event.speed_limit_kmh,
        confidence: event.confidence,
        details: JSON.stringify({
          ...event.details,
          object_class: event.vehicle_class,
          tracking_id: event.tracking_id,
          model_confidence: event.confidence,
          license_plate_confidence: event.license_plate_confidence,
          plate_detection_confidence: event.plate_detection_confidence,
        }),
        location,
        evidencePreview: event.evidence_preview,
        evidenceSuffix: `${event.frame_index}-${event.tracking_id}-${index}`,
        demoId: null,
        sourceVideoName: file.name,
      },
      uploadedAt,
    );

    if (fingerprint) {
      processed = await persistFirebaseProcessed(
        fingerprint,
        file,
        processed,
        uploadedAt,
        processed.evidence.id,
      );
    }
    processedList.push(await trafficStore.add(processed));
  }

  await trafficStore.saveVideo(file.name, file, uploadedAt);
  return { processed: processedList[0], processedList, duplicate: false };
}

export async function ingestVideo(
  file: File,
  options: VideoIngestionOptions = {},
): Promise<{ processed?: ProcessedDetection; processedList?: ProcessedDetection[]; duplicate: boolean }> {
  const rule = findDemoVideoByName(file.name);
  const videoId = rule?.id ?? videoIdFromName(file.name);
  if (!rule) return ingestWithInference(file, videoId, options);
  const cloudEnabled = Boolean(getFirebaseClient());
  const fingerprint = cloudEnabled ? await fingerprintVideo(file) : undefined;
  if (fingerprint) {
    const remote = await findFirebaseProcessed(fingerprint);
    if (remote && !rule) {
      await trafficStore.hydrate();
      return { processed: remote, duplicate: true };
    }
  }
  let existingDemo: ProcessedDetection | undefined;
  if (rule) {
    await trafficStore.hydrate();
    existingDemo = trafficStore.findProcessedByVideo(rule.id, file.name);
  }
  if (!rule && await trafficStore.hasVideo(file.name)) {
    await trafficStore.hydrate();
    const existing = trafficStore.findProcessedByVideo(videoId);
    if (existing) {
      let repaired = existing;
      if (await isBlankEvidencePreview(repaired.evidence.previewDataUrl ?? repaired.incident.evidencePreview)) {
        const preview = await captureFrame(file, rule?.triggerTimestamp ?? existing.incident.videoTimestamp);
        if (!preview) throw new Error("Unable to capture an evidence frame from this video.");
        repaired = {
          incident: { ...existing.incident, evidencePreview: preview },
          evidence: { ...existing.evidence, previewDataUrl: preview },
        };
      }
      if (fingerprint) {
        repaired = await persistFirebaseProcessed(fingerprint, file, repaired, repaired.incident.createdAt ?? new Date().toISOString());
      }
      await trafficStore.updateProcessed(repaired);
      return { processed: repaired, duplicate: true };
    }
  }
  const timestamp = rule?.triggerTimestamp ?? "00:12";
  const cameraId = rule?.cameraId ?? "CAM-001";
  const location = rule?.location ?? "Uploaded video";

  const uploadedAt = new Date().toISOString();
  const preview = await captureFrame(file, timestamp);
  if (!preview) throw new Error("Unable to capture an evidence frame from this video.");
  const sequence = trafficStore.nextSequenceNumbers();
  let processed = new TrafficProcessor(sequence.incident - 1, sequence.evidence - 1).process(
    {
      videoId,
      violation: rule?.violation ?? "Helmetless Riding",
      timestamp,
      cameraId,
      severity: rule?.severity ?? "medium",
      vehicleId: rule?.vehicleId ?? "Bike",
      licensePlate: rule?.licensePlate ?? "BA Pradesh 02 048PA 2762",
      location,
      status: existingDemo?.incident.status,
      evidencePreview: preview,
      sourceVideoName: file.name,
    },
    uploadedAt,
  );

  if (rule) {
    processed = {
      incident: {
        ...processed.incident,
        id: existingDemo?.incident.id ?? processed.incident.id,
        evidenceId: rule.evidenceId,
      },
      evidence: {
        ...processed.evidence,
        id: rule.evidenceId,
        incidentId: existingDemo?.incident.id ?? processed.incident.id,
      },
    };
  }

  if (fingerprint) {
    const suffix = fingerprint.slice(0, 24).toUpperCase();
    const incidentId = existingDemo?.incident.id ?? `INC-${suffix}`;
    const evidenceId = rule?.evidenceId ?? `EVD-${suffix}`;
    processed = {
      incident: { ...processed.incident, id: incidentId, evidenceId },
      evidence: { ...processed.evidence, id: evidenceId, incidentId },
    };
    processed = await persistFirebaseProcessed(fingerprint, file, processed, uploadedAt);
  }

  await trafficStore.saveVideo(file.name, file, uploadedAt);
  if (existingDemo) await trafficStore.updateProcessed(processed);
  else await trafficStore.add(processed);
  return { processed, duplicate: Boolean(existingDemo) };
}

function readImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read evidence image."));
    reader.readAsDataURL(file);
  });
}

export async function attachEvidenceImage(file: File): Promise<ProcessedDetection> {
  const existing = trafficStore.findIncidentForEvidenceImage(file.name);
  if (!existing) throw new Error("Upload a video first so this image can be matched to an incident.");
  const preview = await readImage(file);
  const processed = {
    incident: { ...existing.incident, evidencePreview: preview },
    evidence: { ...existing.evidence, previewDataUrl: preview },
  };
  await trafficStore.updateProcessed(processed);
  return processed;
}