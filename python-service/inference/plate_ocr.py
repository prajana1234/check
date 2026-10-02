from pathlib import Path
import statistics

from fast_alpr import ALPR
from fast_alpr.default_detector import DefaultDetector
from fast_alpr.default_ocr import DefaultOCR
import fast_plate_ocr.inference.hub as ocr_hub
import open_image_models.detection.core.hub as detector_hub

from .detections import PlateDetection

DETECTOR_MODEL = "yolo-v9-t-384-license-plate-end2end"
OCR_MODEL = "cct-s-v2-global-model"


class PlateReader:
    def __init__(self, models_dir: Path) -> None:
        detector_cache = models_dir / "plate-detector"
        ocr_dir = models_dir / "plate-ocr" / OCR_MODEL
        detector_model_dir = detector_cache / DETECTOR_MODEL
        detector_path = detector_model_dir / "yolo-v9-t-384-license-plates-end2end.onnx"
        ocr_path = ocr_dir / "cct_s_v2_global.onnx"
        config_path = ocr_dir / "cct_s_v2_global_plate_config.yaml"
        missing = [path for path in (detector_path, ocr_path, config_path) if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Missing local ALPR model files: " + ", ".join(str(path) for path in missing)
            )

        detector_hub.MODEL_CACHE_DIR = detector_cache
        ocr_hub.MODEL_CACHE_DIR = models_dir / "plate-ocr"
        detector = DefaultDetector(
            model_name=DETECTOR_MODEL,
            providers=["CPUExecutionProvider"],
        )
        ocr = DefaultOCR(
            hub_ocr_model=OCR_MODEL,
            device="cpu",
            providers=["CPUExecutionProvider"],
            model_path=ocr_path,
            config_path=config_path,
        )
        self.alpr = ALPR(detector=detector, ocr=ocr)

    def detect(self, frame) -> list[PlateDetection]:
        detections: list[PlateDetection] = []
        for result in self.alpr.predict(frame):
            box = result.detection.bounding_box
            ocr = result.ocr
            raw_confidence = ocr.confidence if ocr else None
            text_confidence = (
                statistics.fmean(raw_confidence)
                if isinstance(raw_confidence, list) and raw_confidence
                else float(raw_confidence)
                if isinstance(raw_confidence, float)
                else None
            )
            text = ocr.text.strip() if ocr and ocr.text.strip() else None
            detections.append(
                PlateDetection(
                    bbox=(float(box.x1), float(box.y1), float(box.x2), float(box.y2)),
                    confidence=float(result.detection.confidence),
                    text=text,
                    text_confidence=text_confidence,
                )
            )
        return detections
