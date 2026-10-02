import { useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, FileVideo, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app-shell";
import { PageHeader, Section } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { attachEvidenceImage, ingestVideo } from "@/backend/videoIngestion";

const acceptedVideoTypes = ["video/mp4", "video/webm", "video/quicktime"];
const acceptedImageTypes = ["image/jpeg", "image/png", "image/webp"];

type UploadItem = {
  id: string;
  file: File;
  progress: number;
  status: "queued" | "uploading" | "ready";
  previewUrl: string;
};

function getUploadContext(camera: string, title: string): { cameraId: string; location: string } {
  const value = camera.trim() || title.trim();
  const cameraMatch = value.match(/CAM-\d+/i)?.[0].toUpperCase();
  const location = cameraMatch
    ? value.replace(new RegExp(cameraMatch, "i"), "").replace(/^[\s·,.-]+/, "").trim()
    : value;
  return {
    cameraId: cameraMatch ?? "CAM-001",
    location: location || "Uploaded video",
  };
}

export const Route = createFileRoute("/upload")({
  head: () => ({
    meta: [
      { title: "Upload Videos — Nepal Traffic Monitor" },
      { name: "description", content: "Add traffic videos to the local review queue." },
    ],
  }),
  component: UploadPage,
});

function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<UploadItem[]>([]);
  const [title, setTitle] = useState("");
  const [camera, setCamera] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  function addFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    const invalid = files.filter((file) => !acceptedVideoTypes.includes(file.type) && !acceptedImageTypes.includes(file.type));
    if (invalid.length > 0) {
      toast.error("Unsupported file format", { description: "Use MP4, WebM, MOV, JPG, PNG, or WebP files." });
    }

    const valid = files.filter((file) => acceptedVideoTypes.includes(file.type) || acceptedImageTypes.includes(file.type));
    setItems((current) => [
      ...current,
      ...valid.map((file) => ({
        id: `${file.name}-${file.lastModified}-${Math.random()}`,
        file,
        progress: 0,
        status: "queued" as const,
        previewUrl: URL.createObjectURL(file),
      })),
    ]);
  }

  function removeItem(item: UploadItem) {
    URL.revokeObjectURL(item.previewUrl);
    setItems((current) => current.filter((candidate) => candidate.id !== item.id));
  }

  async function startUpload() {
    if (items.length === 0) {
      toast.error("Choose at least one video first");
      return;
    }

    setItems((current) => current.map((item) => ({ ...item, status: "uploading", progress: 10 })));
    try {
      const videos = items.filter((item) => !acceptedImageTypes.includes(item.file.type));
      const images = items.filter((item) => acceptedImageTypes.includes(item.file.type));
      const context = getUploadContext(camera, title);
      for (const item of videos) await ingestVideo(item.file, context);
      for (const item of images) await attachEvidenceImage(item.file);
    } catch (error) {
      toast.error("Video could not be processed", { description: error instanceof Error ? error.message : "Try another video file." });
      setItems((current) => current.map((item) => ({ ...item, status: "queued", progress: 0 })));
      return;
    }
    let progress = 10;
    const timer = window.setInterval(() => {
      progress += 30;
      setItems((current) =>
        current.map((item) => ({
          ...item,
          progress: Math.min(progress, 100),
          status: progress >= 100 ? "ready" : "uploading",
        })),
      );
      if (progress >= 100) {
        window.clearInterval(timer);
        toast.success("Videos added to the review queue");
      }
    }, 350);
  }

  return (
    <AppShell>
      <PageHeader
        title="Upload videos"
        description="Add footage to the local review queue for traffic analysis."
      />
      <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <Section title="Choose video or evidence files" description="MP4, WebM, MOV, JPG, PNG, and WebP files.">
          <div className="p-4">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setIsDragging(false);
                addFiles(event.dataTransfer.files);
              }}
              className={`flex min-h-56 w-full flex-col items-center justify-center border border-dashed px-6 text-center transition-colors ${isDragging ? "border-primary bg-primary/10" : "border-border bg-background hover:border-primary/60 hover:bg-muted/40"}`}
            >
              <UploadCloud className="h-9 w-9 text-primary" />
              <span className="mt-3 text-sm font-semibold">Drop video files here</span>
              <span className="mt-1 text-xs text-muted-foreground">
                or click to browse from this device
              </span>
            </button>
            <input
              ref={inputRef}
              type="file"
              accept="video/mp4,video/webm,video/quicktime,image/jpeg,image/png,image/webp"
              multiple
              className="hidden"
              onChange={(event) => {
                if (event.target.files) addFiles(event.target.files);
                event.target.value = "";
              }}
            />
          </div>
        </Section>
        <Section
          title="Video details"
          description="Apply context before adding footage to the queue."
        >
          <div className="space-y-4 p-4">
            <div className="space-y-2">
              <Label htmlFor="video-title">Title</Label>
              <Input
                id="video-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Koteshwor evening traffic"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="camera-name">Camera or location</Label>
              <Input
                id="camera-name"
                value={camera}
                onChange={(event) => setCamera(event.target.value)}
                placeholder="e.g. CAM-001 · Koteshwor"
              />
            </div>
            <p className="border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              Videos, incident records, and captured evidence are saved in this browser.
            </p>
            <Button type="button" onClick={startUpload} className="w-full">
              <UploadCloud />
              Add to review queue
            </Button>
          </div>
        </Section>
      </div>
      <Section
        title="Upload queue"
        description={
          items.length
            ? `${items.length} video${items.length === 1 ? "" : "s"} selected`
            : "Selected videos will appear here before processing."
        }
      >
        {items.length === 0 ? (
          <div className="flex min-h-32 items-center justify-center px-4 text-sm text-muted-foreground">
            No videos selected
          </div>
        ) : (
          <div className="divide-y divide-border">
            {items.map((item) => (
              <div key={item.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
                <video
                  src={item.previewUrl}
                  className="h-16 w-28 shrink-0 bg-background object-cover"
                  muted
                  preload="metadata"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <FileVideo className="h-4 w-4 shrink-0 text-primary" />
                    <p className="truncate text-sm font-medium">{item.file.name}</p>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {(item.file.size / 1024 / 1024).toFixed(1)} MB{title && ` · ${title}`}
                    {camera && ` · ${camera}`}
                  </p>
                  {item.status !== "queued" && (
                    <Progress value={item.progress} className="mt-2 h-1.5" />
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {item.status === "ready" ? (
                      <span className="flex items-center gap-1 text-success">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Ready
                      </span>
                    ) : item.status === "uploading" ? (
                      `${item.progress}%`
                    ) : (
                      "Queued"
                    )}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove ${item.file.name}`}
                    onClick={() => removeItem(item)}
                  >
                    <X />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </AppShell>
  );
}
