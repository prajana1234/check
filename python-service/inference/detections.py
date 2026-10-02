from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    tracking_id: int | None = None
    source: str = "yolo"

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def footpoint(self) -> tuple[float, float]:
        x1, _, x2, y2 = self.bbox
        return ((x1 + x2) / 2, y2)

    def as_dict(self) -> dict[str, Any]:
        return {
            "class": self.class_name,
            "confidence": self.confidence,
            "bbox": list(self.bbox),
            "tracking_id": self.tracking_id,
            "source": self.source,
        }


@dataclass(frozen=True)
class PlateDetection:
    bbox: tuple[float, float, float, float]
    confidence: float
    text: str | None = None
    text_confidence: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "class": "License Plate",
            "confidence": self.confidence,
            "bbox": list(self.bbox),
            "text": self.text,
            "text_confidence": self.text_confidence,
        }


@dataclass
class FrameDetections:
    frame_index: int
    timestamp_seconds: float
    fps: float
    width: int
    height: int
    objects: list[Detection]
    helmet_objects: list[Detection]
    plates: list[PlateDetection]
    frame: np.ndarray = field(repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "timestamp_seconds": self.timestamp_seconds,
            "timestamp": format_timestamp(self.timestamp_seconds),
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "objects": [item.as_dict() for item in self.objects],
            "helmet_objects": [item.as_dict() for item in self.helmet_objects],
            "plates": [item.as_dict() for item in self.plates],
        }


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}"
