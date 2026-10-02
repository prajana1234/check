export type CameraStatus = "online" | "offline" | "maintenance";
export type CameraMode = "demo" | "live" | "standby";
export type Severity = "critical" | "high" | "medium" | "low";
export type IncidentStatus = "new" | "pending" | "reviewing" | "resolved";
export type ViolationType = "Signal Jumping" | "Overspeeding" | "Helmetless Riding" | "Wrong Lane" | "Triple Riding" | "No Helmet & Triple Riding";

export interface Camera {
  id: string; name: string; location: string; district: string; status: CameraStatus;
  mode: CameraMode; lastHeartbeat: string | null; currentDemoId: string | null;
  androidDeviceId: string | null; installedAt: string;
}

export interface Incident {
  id: string; cameraId: string; violation: ViolationType; vehicleId: string;
  licensePlate: string; speed: number | null; speedLimit: number | null;
  videoTimestamp: string; detectedAt: string; location: string; severity: Severity;
  modelConfidence?: number; detectionDetails?: string;
  status: IncidentStatus; evidenceId: string; evidencePath?: string; evidencePreview?: string; sourceVideoName?: string; sourceVideoPath?: string; createdAt?: string; isHidden?: boolean; demoId: string | null;
}

export interface DemoVideo {
  id: string; name: string; violation: ViolationType; triggerTimestamp: string;
  cameraId: string; evidenceStatus: "ready" | "pending"; status: "available" | "disabled";
  severity: Severity; vehicleId: string; licensePlate: string; location: string; evidenceId: string;
}

export interface Evidence {
  id: string; incidentId: string; violation: ViolationType; cameraId: string;
  videoTimestamp: string; vehicleId: string; licensePlate: string; capturedAt: string;
  confidence?: number; details?: string;
  previewKind: "simulated-placeholder" | "video-frame";
  filename?: string; sourceVideoId?: string; path?: string; previewDataUrl?: string; isHidden?: boolean;
}

export interface SystemUser {
  id: string; name: string; email: string; role: "ADMIN" | "OPERATOR";
  status: "active" | "inactive"; lastActive: string; createdAt: string;
}

export interface AnalyticsData {
  byType: Array<{ name: string; value: number }>;
  byCamera: Array<{ name: string; value: number }>;
  overTime: Array<{ time: string; incidents: number }>;
  bySeverity: Array<{ name: string; value: number }>;
  daily: Array<{ day: string; incidents: number }>;
  weekly: Array<{ week: string; incidents: number }>;
}

export interface ApiResponse<T> { data: T; generatedAt: string; source: "demo"; }