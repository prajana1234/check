from pathlib import Path

from ultralytics import YOLO

from .detections import Detection

VEHICLE_CLASSES = {"bicycle", "motorcycle", "car", "bus", "truck"}
TRACKED_CLASSES = VEHICLE_CLASSES | {"person", "traffic light"}


class YoloDetector:
    def __init__(self, weights: Path, device: str = "cpu") -> None:
        if not weights.is_file():
            raise FileNotFoundError(f"YOLO COCO weights not found: {weights}")
        self.model = YOLO(str(weights))
        self.device = device

    def reset(self) -> None:
        predictor = getattr(self.model, "predictor", None)
        for tracker in getattr(predictor, "trackers", []):
            tracker.reset()

    def detect_and_track(self, frame) -> list[Detection]:
        results = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            device=self.device,
            verbose=False,
        )
        if not results:
            return []

        result = results[0]
        detections: list[Detection] = []
        for index, box in enumerate(result.boxes):
            class_id = int(box.cls.item())
            class_name = str(result.names[class_id]).lower()
            if class_name not in TRACKED_CLASSES:
                continue
            coordinates = tuple(float(value) for value in box.xyxy[0].tolist())
            track_id = None
            if result.boxes.id is not None:
                track_id = int(result.boxes.id[index].item())
            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=float(box.conf.item()),
                    bbox=coordinates,
                    tracking_id=track_id,
                )
            )
        return detections
