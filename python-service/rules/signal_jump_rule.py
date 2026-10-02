import cv2
import numpy as np

from inference.detections import FrameDetections
from .geometry import polygon_contains, signed_line_side

VEHICLE_CLASSES = {"bicycle", "motorcycle", "car", "bus", "truck"}


def _red_signal_visible(frame: FrameDetections, config: dict) -> bool:
    region = config.get("traffic_light_region", [])
    if len(region) < 3:
        return False
    detected_light = any(
        item.class_name == "traffic light"
        and item.confidence >= float(config.get("traffic_light_confidence", 0.35))
        and polygon_contains((item.center[0] / frame.width, item.center[1] / frame.height), region)
        for item in frame.objects
    )
    if not detected_light:
        return False

    points = np.asarray(
        [[round(x * frame.width), round(y * frame.height)] for x, y in region],
        dtype=np.int32,
    )
    mask = np.zeros(frame.frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [points], 255)
    hsv = cv2.cvtColor(frame.frame, cv2.COLOR_BGR2HSV)
    red_low = cv2.inRange(hsv, np.asarray([0, 70, 60]), np.asarray([12, 255, 255]))
    red_high = cv2.inRange(hsv, np.asarray([168, 70, 60]), np.asarray([180, 255, 255]))
    colored_pixels = cv2.countNonZero(cv2.bitwise_and(cv2.bitwise_or(red_low, red_high), mask))
    region_pixels = cv2.countNonZero(mask)
    if region_pixels == 0:
        return False
    return colored_pixels / region_pixels >= float(config.get("red_pixel_ratio", 0.015))


def evaluate(
    frame: FrameDetections,
    camera_config: dict,
    previous_positions: dict[int, tuple[float, float]],
    confidence_threshold: float,
    emitted: set[tuple[str, int | None]],
) -> list[dict]:
    line = camera_config.get("stop_line", [])
    if len(line) != 2 or not _red_signal_visible(frame, camera_config):
        return []
    events = []
    for vehicle in frame.objects:
        if (
            vehicle.class_name not in VEHICLE_CLASSES
            or vehicle.confidence < confidence_threshold
            or vehicle.tracking_id is None
        ):
            continue
        current = (vehicle.footpoint[0] / frame.width, vehicle.footpoint[1] / frame.height)
        previous = previous_positions.get(vehicle.tracking_id)
        if previous is None:
            continue
        previous_side = signed_line_side(previous, line)
        current_side = signed_line_side(current, line)
        if previous_side * current_side >= 0:
            continue
        crossing_fraction = previous_side / (previous_side - current_side)
        crossing_point = (
            previous[0] + crossing_fraction * (current[0] - previous[0]),
            previous[1] + crossing_fraction * (current[1] - previous[1]),
        )
        line_dx = line[1][0] - line[0][0]
        line_dy = line[1][1] - line[0][1]
        line_length_squared = line_dx * line_dx + line_dy * line_dy
        if line_length_squared == 0:
            continue
        line_position = (
            (crossing_point[0] - line[0][0]) * line_dx
            + (crossing_point[1] - line[0][1]) * line_dy
        ) / line_length_squared
        if not 0 <= line_position <= 1:
            continue
        key = ("signal-jump", vehicle.tracking_id)
        if key in emitted:
            continue
        emitted.add(key)
        events.append(
            {
                "violation": "Signal Jumping",
                "confidence": vehicle.confidence,
                "tracking_id": vehicle.tracking_id,
                "vehicle_class": vehicle.class_name,
                "vehicle_detection": vehicle,
                "severity": "critical",
                "details": {
                    "rule": "tracked vehicle crossed the configured stop line while the detected traffic-light region was visibly red",
                    "signal_state": "red",
                    "stop_line": line,
                },
            }
        )
    return events
