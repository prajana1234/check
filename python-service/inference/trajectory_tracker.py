from collections import defaultdict, deque
from dataclasses import dataclass

import cv2
import numpy as np

from .detections import Detection


@dataclass(frozen=True)
class TrackSample:
    timestamp_seconds: float
    point: tuple[float, float]
    speed_kmh: float | None


class TrajectoryTracker:
    def __init__(self, max_samples: int = 48) -> None:
        self._samples: dict[int, deque[TrackSample]] = defaultdict(
            lambda: deque(maxlen=max_samples)
        )

    def reset(self) -> None:
        self._samples.clear()

    def update(
        self,
        detections: list[Detection],
        timestamp_seconds: float,
        homography: list[list[float]] | None,
        minimum_interval_seconds: float,
    ) -> dict[int, float | None]:
        speeds: dict[int, float | None] = {}
        for detection in detections:
            track_id = detection.tracking_id
            if track_id is None or detection.class_name not in {
                "bicycle",
                "motorcycle",
                "car",
                "bus",
                "truck",
            }:
                continue
            point = detection.footpoint
            sample_point = self._project(point, homography) if homography else None
            if homography and sample_point is None:
                continue
            prior = self._samples[track_id]
            speed = None
            if sample_point is not None and prior:
                previous = next(
                    (
                        sample
                        for sample in reversed(prior)
                        if timestamp_seconds - sample.timestamp_seconds
                        >= minimum_interval_seconds
                    ),
                    None,
                )
                if previous:
                    elapsed = timestamp_seconds - previous.timestamp_seconds
                    if elapsed > 0:
                        distance = float(np.linalg.norm(np.subtract(sample_point, previous.point)))
                        speed = distance / elapsed * 3.6
            prior.append(
                TrackSample(
                    timestamp_seconds,
                    sample_point if sample_point is not None else point,
                    speed,
                )
            )
            speeds[track_id] = speed
        return speeds

    @staticmethod
    def _project(
        point: tuple[float, float], homography: list[list[float]]
    ) -> tuple[float, float] | None:
        matrix = np.asarray(homography, dtype=np.float64)
        if matrix.shape != (3, 3):
            raise ValueError("speed_homography must be a 3x3 image-to-meter matrix")
        projected = cv2.perspectiveTransform(
            np.asarray([[point]], dtype=np.float32), matrix.astype(np.float32)
        )[0][0]
        if not np.isfinite(projected).all():
            return None
        return float(projected[0]), float(projected[1])
