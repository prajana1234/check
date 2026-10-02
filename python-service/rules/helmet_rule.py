from inference.detections import Detection, FrameDetections
from .geometry import associate_person_to_motorcycle, point_in_bbox


def evaluate(
    frame: FrameDetections,
    confidence_threshold: float,
    emitted: set[tuple[str, int | None]],
) -> list[dict]:
    people = [
        item
        for item in frame.objects
        if item.class_name == "person" and item.confidence >= confidence_threshold
    ]
    motorcycles = [
        item
        for item in frame.objects
        if item.class_name == "motorcycle" and item.confidence >= confidence_threshold
    ]
    events = []
    for helmet in frame.helmet_objects:
        if helmet.class_name.lower().replace("_", " ") != "without helmet":
            continue
        if helmet.confidence < confidence_threshold:
            continue
        center = helmet.center
        person = next(
            (
                item
                for item in people
                if item.tracking_id is not None and point_in_bbox(center, item.bbox)
            ),
            None,
        )
        if person is None:
            continue
        motorcycle = associate_person_to_motorcycle(
            person, motorcycles, frame.width, frame.height
        )
        if motorcycle is None or motorcycle.tracking_id is None:
            continue
        key = ("helmet", motorcycle.tracking_id)
        if key in emitted:
            continue
        emitted.add(key)
        events.append(
            {
                "violation": "Helmetless Riding",
                "confidence": min(helmet.confidence, person.confidence, motorcycle.confidence),
                "tracking_id": motorcycle.tracking_id,
                "vehicle_class": "motorcycle",
                "vehicle_detection": motorcycle,
                "details": {
                    "rule": "without-helmet detector overlaps a tracked person associated with a motorcycle",
                    "helmet_confidence": helmet.confidence,
                    "person_confidence": person.confidence,
                },
            }
        )
    return events
