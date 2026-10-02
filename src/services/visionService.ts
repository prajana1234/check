import type { Severity, ViolationType } from "@/types";

export type VisionIncidentEvent = {
  violation: ViolationType;
  confidence: number;
  tracking_id: number;
  vehicle_class: string;
  vehicle_id: string;
  license_plate: string | null;
  license_plate_confidence: number | null;
  plate_detection_confidence?: number;
  speed_kmh: number | null;
  speed_limit_kmh: number | null;
  timestamp: string;
  timestamp_seconds: number;
  frame_index: number;
  camera_id: string;
  severity?: Severity;
  details: Record<string, unknown>;
  evidence_preview: string;
};

export type VisionAnalysis = {
  camera_id: string;
  fps: number;
  frame_count: number;
  analyzed_frame_count: number;
  frame_stride: number;
  enabled_rules: Record<string, boolean>;
  detections: Array<{
    frame_index: number;
    timestamp: string;
    timestamp_seconds: number;
    fps: number;
    objects: Array<{
      class: string;
      confidence: number;
      bbox: [number, number, number, number];
      tracking_id: number | null;
      source: string;
    }>;
    helmet_objects: Array<{
      class: string;
      confidence: number;
      bbox: [number, number, number, number];
      tracking_id: number | null;
      source: string;
    }>;
    plates: Array<{
      class: string;
      confidence: number;
      bbox: [number, number, number, number];
      text: string | null;
      text_confidence: number | null;
    }>;
  }>;
  incidents: VisionIncidentEvent[];
};

const visionServiceUrl = import.meta.env.VITE_VISION_API_URL ?? "http://127.0.0.1:8010";

export async function analyzeUploadedVideo(
  file: File,
  cameraId: string,
): Promise<VisionAnalysis> {
  const body = new FormData();
  body.append("file", file, file.name);
  body.append("camera_id", cameraId);

  let response: Response;
  try {
    response = await fetch(`${visionServiceUrl}/api/vision/analyze`, {
      method: "POST",
      body,
    });
  } catch {
    throw new Error(
      "The local vision service is unavailable. Start it with python-service/run.ps1, then retry the upload.",
    );
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    throw new Error(payload?.detail ?? `Video inference failed (${response.status}).`);
  }

  return (await response.json()) as VisionAnalysis;
}
