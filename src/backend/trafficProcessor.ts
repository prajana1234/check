import type { DemoVideo, Evidence, Incident, IncidentStatus, Severity, ViolationType } from "@/types";

export type VideoDetection = {
  videoId: string;
  violation: ViolationType;
  timestamp: string;
  cameraId: string;
  severity: Severity;
  vehicleId?: string;
  licensePlate?: string;
  location?: string;
  status?: IncidentStatus;
  evidencePreview?: string;
  sourceVideoName?: string;
  demoId?: string | null;
  speed?: number | null;
  speedLimit?: number | null;
  confidence?: number;
  details?: string;
  evidenceSuffix?: string;
};

export type ProcessedDetection = {
  incident: Incident;
  evidence: Evidence;
};

const timestampPattern = /^\d{2}:\d{2}(?::\d{2})?$/;

function normalizeTimestamp(timestamp: string): string {
  if (!timestampPattern.test(timestamp)) {
    throw new Error(`Invalid video timestamp "${timestamp}". Use MM:SS or HH:MM:SS.`);
  }

  return timestamp;
}

function evidenceFilename(videoId: string, timestamp: string, suffix?: string): string {
  const safeSuffix = suffix ? `_${suffix.replace(/[^a-zA-Z0-9_-]/g, "_")}` : "";
  return `${videoId}_${timestamp.replaceAll(":", "-")}${safeSuffix}.jpg`;
}

export class TrafficProcessor {
  private incidentSequence: number;
  private evidenceSequence: number;

  constructor(lastIncidentNumber = 0, lastEvidenceNumber = 0) {
    this.incidentSequence = lastIncidentNumber;
    this.evidenceSequence = lastEvidenceNumber;
  }

  process(detection: VideoDetection, detectedAt = new Date().toISOString()): ProcessedDetection {
    const timestamp = normalizeTimestamp(detection.timestamp);
    const incidentNumber = ++this.incidentSequence;
    const evidenceNumber = ++this.evidenceSequence;
    const incidentId = `INC-${String(incidentNumber).padStart(4, "0")}`;
    const evidenceId = `EVD-${String(evidenceNumber).padStart(6, "0")}`;
    const filename = evidenceFilename(detection.videoId, timestamp, detection.evidenceSuffix);
    const evidencePath = `/evidence/${filename}`;

    const evidence: Evidence = {
      id: evidenceId,
      incidentId,
      violation: detection.violation,
      cameraId: detection.cameraId,
      videoTimestamp: timestamp,
      vehicleId: detection.vehicleId ?? "UNKNOWN",
      licensePlate: detection.licensePlate ?? "UNKNOWN",
      capturedAt: detectedAt,
      previewKind: "video-frame",
      filename,
      sourceVideoId: detection.videoId,
      path: evidencePath,
      previewDataUrl: detection.evidencePreview,
      confidence: detection.confidence,
      details: detection.details,
    };

    const incident: Incident = {
      id: incidentId,
      cameraId: detection.cameraId,
      violation: detection.violation,
      vehicleId: detection.vehicleId ?? "UNKNOWN",
      licensePlate: detection.licensePlate ?? "UNKNOWN",
      speed: detection.speed ?? null,
      speedLimit: detection.speedLimit ?? null,
      videoTimestamp: timestamp,
      detectedAt,
      location: detection.location ?? "Unknown location",
      severity: detection.severity,
      status: detection.status ?? "new",
      evidenceId,
      evidencePath,
      evidencePreview: detection.evidencePreview,
      modelConfidence: detection.confidence,
      detectionDetails: detection.details,
      sourceVideoName: detection.sourceVideoName,
      createdAt: detectedAt,
      demoId: detection.demoId === undefined ? detection.videoId : detection.demoId,
    };

    return { incident, evidence };
  }

  processDemo(video: DemoVideo, detectedAt?: string): ProcessedDetection {
    return this.process(
      {
        videoId: video.id,
        violation: video.violation,
        timestamp: video.triggerTimestamp,
        cameraId: video.cameraId,
        severity: video.severity,
        vehicleId: video.vehicleId,
        licensePlate: video.licensePlate,
        location: video.location,
      },
      detectedAt,
    );
  }
}