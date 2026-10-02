from pathlib import Path
from collections.abc import Callable

import cv2

from .detections import FrameDetections
from .helmet_detector import HelmetDetector
from .plate_ocr import PlateReader
from .yolo_detector import YoloDetector


class VideoAnalyzer:
    def __init__(self, models_dir: Path, device: str = "cpu") -> None:
        self.yolo = YoloDetector(models_dir / "yolov8n.pt", device=device)
        self.helmet = HelmetDetector(models_dir / "helmet-best.pt", device=device)
        self.plates = PlateReader(models_dir)

    def reset(self) -> None:
        self.yolo.reset()

    def analyze(
        self,
        video_path: Path,
        frame_stride: int,
        on_frame: Callable[[FrameDetections], None],
    ) -> dict[str, float | int]:
        if frame_stride < 1:
            raise ValueError("frame_stride must be at least 1")
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise ValueError("The uploaded video could not be opened by OpenCV")

        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if fps <= 0:
            capture.release()
            raise ValueError("The video has no valid FPS metadata")
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0 or frame_count <= 0:
            capture.release()
            raise ValueError("The uploaded video has no readable frames")

        frame_index = 0
        analyzed_frames = 0
        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break
                if frame_index % frame_stride == 0:
                    timestamp = frame_index / fps
                    objects = self.yolo.detect_and_track(frame)
                    helmets = self.helmet.detect(frame)
                    plates = self.plates.detect(frame)
                    on_frame(
                        FrameDetections(
                            frame_index=frame_index,
                            timestamp_seconds=timestamp,
                            fps=fps,
                            width=width,
                            height=height,
                            objects=objects,
                            helmet_objects=helmets,
                            plates=plates,
                            frame=frame,
                        )
                    )
                    analyzed_frames += 1
                frame_index += 1
        finally:
            capture.release()
        if not analyzed_frames:
            raise ValueError("No frames were analyzed")
        return {"fps": fps, "frame_count": frame_count, "analyzed_frames": analyzed_frames}
