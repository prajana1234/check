import base64
import json
from pathlib import Path

import cv2

from inference.detections import FrameDetections, format_timestamp
from inference.trajectory_tracker import TrajectoryTracker
from rules import helmet_rule, overspeed_rule, signal_jump_rule, triple_riding_rule, wrong_lane_rule

VEHICLE_CLASSES = {"bicycle", "motorcycle", "car", "bus", "truck"}


class RuleEngine:
    def __init__(self, config_path: Path) -> None:
        with config_path.open("r", encoding="utf-8") as config_file:
            self.config = json.load(config_file)
        self.analysis_config = self.config.get("analysis", {})
        self.trajectory = TrajectoryTracker()
        self.emitted: set[tuple[str, int | None]] = set()
        self.previous_positions: dict[int, tuple[float, float]] = {}
        self.camera_config: dict = {}

    def start_video(self, camera_id: str) -> None:
        self.trajectory.reset()
        self.emitted.clear()
        self.previous_positions.clear()
        self.camera_id = camera_id
        self.camera_config = self.config.get("cameras", {}).get(camera_id, {})

    def process_frame(self, frame: FrameDetections) -> list[dict]:
        confidence_threshold = float(self.analysis_config.get("confidence_threshold", 0.35))
        speed_limit = self.camera_config.get("speed_limit_kmh")
        homography = self.camera_config.get("speed_homography")
        minimum_interval = float(
            self.analysis_config.get("speed_minimum_interval_seconds", 0.5)
        )
        speeds = self.trajectory.update(
            frame.objects,
            frame.timestamp_seconds,
            homography,
            minimum_interval,
        )
        events = [
            *helmet_rule.evaluate(
                frame,
                float(self.analysis_config.get("helmet_confidence_threshold", 0.35)),
                self.emitted,
            ),
            *triple_riding_rule.evaluate(
                frame,
                confidence_threshold,
                self.emitted,
            ),
            *wrong_lane_rule.evaluate(
                frame,
                self.camera_config,
                self.previous_positions,
                confidence_threshold,
                self.emitted,
            ),
            *signal_jump_rule.evaluate(
                frame,
                self.camera_config,
                self.previous_positions,
                confidence_threshold,
                self.emitted,
            ),
            *overspeed_rule.evaluate(
                frame,
                self.camera_config,
                speeds,
                confidence_threshold,
                self.emitted,
            ),
        ]
        evidence_preview = None
        if events:
            image_quality = int(self.analysis_config.get("jpeg_quality", 88))
            encoded_successfully, encoded = cv2.imencode(
                ".jpg",
                frame.frame,
                [cv2.IMWRITE_JPEG_QUALITY, image_quality],
            )
            if not encoded_successfully:
                raise ValueError("Could not encode the violation evidence frame")
            evidence_preview = (
                "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")
            )

        for event in events:
            detection = event.pop("vehicle_detection")
            event["timestamp"] = format_timestamp(frame.timestamp_seconds)
            event["timestamp_seconds"] = frame.timestamp_seconds
            event["frame_index"] = frame.frame_index
            event["vehicle_id"] = f"{event['vehicle_class']}-{event['tracking_id']}"
            event["license_plate"] = None
            event["license_plate_confidence"] = None
            event["speed_limit_kmh"] = event.get("speed_limit_kmh", speed_limit)
            event["evidence_preview"] = evidence_preview
            event["camera_id"] = self.camera_id

            matching_plates = [
                plate
                for plate in frame.plates
                if _contains(detection.bbox, _center(plate.bbox))
                and plate.text
                and plate.text_confidence is not None
                and plate.text_confidence
                >= float(
                    self.analysis_config.get("plate_text_confidence_threshold", 0.6)
                )
            ]
            if matching_plates:
                plate = max(matching_plates, key=lambda item: item.confidence)
                event["license_plate"] = plate.text
                event["license_plate_confidence"] = plate.text_confidence
                event["plate_detection_confidence"] = plate.confidence
            event["speed_kmh"] = event.get("speed_kmh")

        self.previous_positions = {
            item.tracking_id: (
                item.footpoint[0] / frame.width,
                item.footpoint[1] / frame.height,
            )
            for item in frame.objects
            if item.class_name in VEHICLE_CLASSES and item.tracking_id is not None
        }
        return events

    def enabled_rules(self) -> dict[str, bool]:
        return {
            "helmetless_riding": True,
            "triple_riding": True,
            "wrong_lane": bool(self.camera_config.get("lanes")),
            "signal_jumping": bool(
                self.camera_config.get("stop_line")
                and self.camera_config.get("traffic_light_region")
            ),
            "overspeeding": bool(
                self.camera_config.get("speed_limit_kmh")
                and self.camera_config.get("speed_homography")
            ),
        }


def _center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def _contains(
    bbox: tuple[float, float, float, float], point: tuple[float, float]
) -> bool:
    return bbox[0] <= point[0] <= bbox[2] and bbox[1] <= point[1] <= bbox[3]
