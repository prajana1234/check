from math import hypot

from inference.detections import FrameDetections
from .geometry import polygon_contains

VEHICLE_CLASSES = {"bicycle", "motorcycle", "car", "bus", "truck"}


def evaluate(
    frame: FrameDetections,
    camera_config: dict,
    previous_positions: dict[int, tuple[float, float]],
    confidence_threshold: float,
    emitted: set[tuple[str, int | None]],
) -> list[dict]:
    lanes = camera_config.get("lanes", [])
    if not lanes:
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
        if previous is None or hypot(current[0] - previous[0], current[1] - previous[1]) < 0.002:
            continue
        for lane in lanes:
            polygon = lane.get("polygon", [])
            direction = lane.get("expected_direction")
            if len(polygon) < 3 or not direction or not polygon_contains(current, polygon):
                continue
            direction_length = hypot(float(direction[0]), float(direction[1]))
            if direction_length == 0:
                continue
            observed = (current[0] - previous[0], current[1] - previous[1])
            expected = (float(direction[0]) / direction_length, float(direction[1]) / direction_length)
            dot = observed[0] * expected[0] + observed[1] * expected[1]
            observed_length = hypot(*observed)
            alignment = dot / observed_length if observed_length else 0.0
            if alignment >= -float(lane.get("opposite_direction_cosine", 0.5)):
                continue
            key = ("wrong-lane", vehicle.tracking_id)
            if key in emitted:
                break
            emitted.add(key)
            events.append(
                {
                    "violation": "Wrong Lane",
                    "confidence": vehicle.confidence,
                    "tracking_id": vehicle.tracking_id,
                    "vehicle_class": vehicle.class_name,
                    "vehicle_detection": vehicle,
                    "severity": "high",
                    "details": {
                        "rule": "vehicle is inside a configured lane polygon and its tracked travel direction opposes the configured lane direction",
                        "lane_id": lane.get("id", "unnamed"),
                        "direction_alignment": round(alignment, 4),
                    },
                }
            )
            break
    return events
