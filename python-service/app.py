import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from inference.video_analyzer import VideoAnalyzer
from rules.engine import RuleEngine

SERVICE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SERVICE_DIR.parent
MODELS_DIR = PROJECT_ROOT / "models"
CONFIG_PATH = SERVICE_DIR / "config" / "traffic_rules.json"
MAX_UPLOAD_BYTES = int(os.environ.get("TRINETRA_MAX_UPLOAD_BYTES", 500 * 1024 * 1024))

app = FastAPI(title="TriNetra Local Vision Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

analyzer: VideoAnalyzer | None = None
rule_engine: RuleEngine | None = None


def _initialize_models() -> None:
    global analyzer, rule_engine
    if analyzer is not None and rule_engine is not None:
        return
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        import json

        settings = json.load(config_file)
    device = str(settings.get("analysis", {}).get("device", "cpu"))
    analyzer = VideoAnalyzer(MODELS_DIR, device=device)
    rule_engine = RuleEngine(CONFIG_PATH)


@app.on_event("startup")
async def load_local_models() -> None:
    await run_in_threadpool(_initialize_models)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ready" if analyzer is not None and rule_engine is not None else "starting",
        "device": "cpu",
        "models_directory": str(MODELS_DIR),
    }


def _analyze_file(video_path: Path, camera_id: str) -> dict:
    if analyzer is None or rule_engine is None:
        _initialize_models()
    assert analyzer is not None and rule_engine is not None
    analyzer.reset()
    rule_engine.start_video(camera_id)
    detections: list[dict] = []
    incidents: list[dict] = []

    def process_frame(frame) -> None:
        detections.append(frame.as_dict())
        incidents.extend(rule_engine.process_frame(frame))

    metadata = analyzer.analyze(
        video_path,
        frame_stride=int(rule_engine.analysis_config.get("frame_stride", 3)),
        on_frame=process_frame,
    )
    return {
        "camera_id": camera_id,
        "fps": metadata["fps"],
        "frame_count": metadata["frame_count"],
        "analyzed_frame_count": metadata["analyzed_frames"],
        "frame_stride": int(rule_engine.analysis_config.get("frame_stride", 3)),
        "enabled_rules": rule_engine.enabled_rules(),
        "detections": detections,
        "incidents": incidents,
    }


@app.post("/api/vision/analyze")
async def analyze_video(
    file: UploadFile = File(...),
    camera_id: str = Form("CAM-001"),
) -> dict:
    extension = Path(file.filename or "upload.mp4").suffix.lower()
    if extension not in {".mp4", ".mov", ".webm", ".mkv", ".avi"}:
        raise HTTPException(status_code=415, detail="Upload a supported video file")

    temporary_path: Path | None = None
    total_bytes = 0
    try:
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temporary_file:
            temporary_path = Path(temporary_file.name)
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Video exceeds the local service size limit")
                temporary_file.write(chunk)
        return await run_in_threadpool(_analyze_file, temporary_path, camera_id)
    except HTTPException:
        raise
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Video inference failed: {error}") from error
    finally:
        await file.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
