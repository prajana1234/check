from pathlib import Path

from ultralytics import YOLO

from .detections import Detection


class HelmetDetector:
    def __init__(self, weights: Path, device: str = "cpu") -> None:
        if not weights.is_file():
            raise FileNotFoundError(f"Helmet weights not found: {weights}")
        self.model = YOLO(str(weights))
        self.device = device

    def detect(self, frame) -> list[Detection]:
        results = self.model.predict(frame, device=self.device, verbose=False)
        if not results:
            return []

        result = results[0]
        detections: list[Detection] = []
        for box in result.boxes:
            class_id = int(box.cls.item())
            class_name = str(result.names[class_id])
            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=float(box.conf.item()),
                    bbox=tuple(float(value) for value in box.xyxy[0].tolist()),
                    source="helmet-yolo",
                )
            )
        return detections
