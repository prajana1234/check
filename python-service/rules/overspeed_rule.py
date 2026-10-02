from inference.detections import FrameDetections

VEHICLE_CLASSES = {"bicycle", "motorcycle", "car", "bus", "truck"}


def evaluate(
    frame: FrameDetections,
    camera_config: dict,
    speeds_kmh: dict[int, float | None],
    confidence_threshold: float,
    emitted: set[tuple[str, int | None]],
) -> list[dict]:
    speed_limit = camera_config.get("speed_limit_kmh")
    homography = camera_config.get("speed_homography")
    if speed_limit is None or homography is None:
        return []
    speed_limit = float(speed_limit)
    if speed_limit <= 0:
        return []

    detections = {item.tracking_id: item for item in frame.objects if item.class_name in VEHICLE_CLASSES}
    events = []
    for track_id, speed in speeds_kmh.items():
        detection = detections.get(track_id)
        if (
            detection is None
            or detection.confidence < confidence_threshold
            or speed is None
            or speed <= speed_limit
        ):
            continue
        key = ("overspeed", track_id)
        if key in emitted:
            continue
        emitted.add(key)
        events.append(
            {
                "violation": "Overspeeding",
                "confidence": detection.confidence,
                "tracking_id": track_id,
                "vehicle_class": detection.class_name,
                "vehicle_detection": detection,
                "speed_kmh": round(speed, 2),
                "speed_limit_kmh": speed_limit,
                "severity": "high" if speed <= speed_limit * 1.25 else "critical",
                "details": {
                    "rule": "image footpoint transformed to ground-plane meters by configured homography; displacement divided by frame-timestamp interval",
                    "speed_method": "homography-ground-plane-distance-over-time",
                },
            }
        )
    return events
