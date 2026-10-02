import {
  collection,
  doc,
  getDoc,
  getDocs,
  setDoc,
  writeBatch,
} from "firebase/firestore";
import { getDownloadURL, ref, uploadBytes } from "firebase/storage";
import type { Evidence, Incident } from "@/types";
import type { ProcessedDetection } from "./trafficProcessor";
import { getFirebaseClient } from "./firebaseClient";

function requireFirebaseUser() {
  const client = getFirebaseClient();
  if (!client) return undefined;
  if (!client.auth.currentUser) throw new Error("Sign in to save videos and evidence to Firebase.");
  return client;
}

export async function fingerprintVideo(file: File): Promise<string> {
  const sampleSize = 64 * 1024;
  const offsets = [0, Math.max(0, Math.floor(file.size / 2) - sampleSize / 2), Math.max(0, file.size - sampleSize)];
  const samples = await Promise.all(offsets.map((offset) => file.slice(offset, offset + sampleSize).arrayBuffer()));
  const bytes = new Uint8Array(8 + samples.reduce((total, sample) => total + sample.byteLength, 0));
  new DataView(bytes.buffer).setBigUint64(0, BigInt(file.size));
  let offset = 8;
  for (const sample of samples) {
    bytes.set(new Uint8Array(sample), offset);
    offset += sample.byteLength;
  }
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function findFirebaseProcessed(fingerprint: string): Promise<ProcessedDetection | undefined> {
  const client = requireFirebaseUser();
  if (!client) return undefined;
  const manifest = await getDoc(doc(client.database, "videos", fingerprint));
  if (!manifest.exists()) return undefined;
  const ids = manifest.data() as { incidentId: string; evidenceId: string };
  const [incidentSnapshot, evidenceSnapshot] = await Promise.all([
    getDoc(doc(client.database, "incidents", ids.incidentId)),
    getDoc(doc(client.database, "evidence", ids.evidenceId)),
  ]);
  if (!incidentSnapshot.exists() || !evidenceSnapshot.exists()) return undefined;
  return {
    incident: incidentSnapshot.data() as Incident,
    evidence: evidenceSnapshot.data() as Evidence,
  };
}

export async function persistFirebaseProcessed(
  fingerprint: string,
  file: File,
  processed: ProcessedDetection,
  uploadedAt: string,
  evidenceKey?: string,
): Promise<ProcessedDetection> {
  const client = requireFirebaseUser();
  if (!client) return processed;
  const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 120) || "source-video";
  const videoPath = `traffic-videos/${fingerprint}/${safeName}`;
  const evidencePath = evidenceKey
    ? `traffic-evidence/${fingerprint}/${evidenceKey}.jpg`
    : `traffic-evidence/${fingerprint}.jpg`;
  const videoUpload = await uploadBytes(ref(client.storage, videoPath), file, { contentType: file.type });
  const previewBlob = await fetch(processed.evidence.previewDataUrl ?? "").then((response) => {
    if (!response.ok) throw new Error("Could not read the captured evidence image.");
    return response.blob();
  });
  const evidenceUpload = await uploadBytes(ref(client.storage, evidencePath), previewBlob, { contentType: "image/jpeg" });
  const [videoUrl, evidenceUrl] = await Promise.all([
    getDownloadURL(videoUpload.ref),
    getDownloadURL(evidenceUpload.ref),
  ]);
  const saved: ProcessedDetection = {
    incident: { ...processed.incident, evidencePreview: evidenceUrl, sourceVideoPath: videoPath },
    evidence: { ...processed.evidence, path: evidencePath, previewDataUrl: evidenceUrl },
  };
  const batch = writeBatch(client.database);
  batch.set(doc(client.database, "incidents", saved.incident.id), saved.incident);
  batch.set(doc(client.database, "evidence", saved.evidence.id), saved.evidence);
  batch.set(doc(client.database, "videos", fingerprint), {
    id: fingerprint,
    incidentId: saved.incident.id,
    evidenceId: saved.evidence.id,
    name: file.name,
    size: file.size,
    uploadedAt,
    storagePath: videoPath,
    downloadUrl: videoUrl,
  });
  await batch.commit();
  return saved;
}

export async function listFirebaseRecords(): Promise<{ incidents: Incident[]; evidence: Evidence[] }> {
  const client = getFirebaseClient();
  if (!client || !client.auth.currentUser) return { incidents: [], evidence: [] };
  const [incidentSnapshots, evidenceSnapshots] = await Promise.all([
    getDocs(collection(client.database, "incidents")),
    getDocs(collection(client.database, "evidence")),
  ]);
  return {
    incidents: incidentSnapshots.docs.map((snapshot) => snapshot.data() as Incident),
    evidence: evidenceSnapshots.docs.map((snapshot) => snapshot.data() as Evidence),
  };
}

export async function saveFirebaseProcessed(processed: ProcessedDetection): Promise<void> {
  const client = requireFirebaseUser();
  if (!client) return;
  const batch = writeBatch(client.database);
  batch.set(doc(client.database, "incidents", processed.incident.id), processed.incident, { merge: true });
  batch.set(doc(client.database, "evidence", processed.evidence.id), processed.evidence, { merge: true });
  await batch.commit();
}

export async function hideFirebaseIncident(incident: Incident, evidence?: Evidence): Promise<void> {
  const client = requireFirebaseUser();
  if (!client) return;
  const batch = writeBatch(client.database);
  batch.set(doc(client.database, "incidents", incident.id), { isHidden: true }, { merge: true });
  if (evidence) batch.set(doc(client.database, "evidence", evidence.id), { isHidden: true }, { merge: true });
  await batch.commit();
}

export async function hideFirebaseEvidence(evidence: Evidence): Promise<void> {
  const client = requireFirebaseUser();
  if (!client) return;
  await setDoc(doc(client.database, "evidence", evidence.id), { isHidden: true }, { merge: true });
}
