from inference.detections import FrameDetections
from .geometry import associate_person_to_motorcycle


def evaluate(
    frame: FrameDetections,
    confidence_threshold: float,
    emitted: set[tuple[str, int | None]],
) -> list[dict]:
    people = [item for item in frame.objects if item.class_name == "person"]
    motorcycles = [item for item in frame.objects if item.class_name == "motorcycle"]
    events = []
    for motorcycle in motorcycles:
        if motorcycle.confidence < confidence_threshold or motorcycle.tracking_id is None:
            continue
        riders = [
            person
            for person in people
            if person.confidence >= confidence_threshold
            and person.tracking_id is not None
            and associate_person_to_motorcycle(
                person, [motorcycle], frame.width, frame.height
            ) is motorcycle
        ]
        if len(riders) < 3:
            continue
        key = ("triple-riding", motorcycle.tracking_id)
        if key in emitted:
            continue
        emitted.add(key)
        events.append(
            {
                "violation": "Triple Riding",
                "confidence": min([motorcycle.confidence, *(person.confidence for person in riders)]),
                "tracking_id": motorcycle.tracking_id,
                "vehicle_class": "motorcycle",
                "vehicle_detection": motorcycle,
                "details": {
                    "rule": "at least three distinct tracked person detections are spatially associated with one tracked motorcycle",
                    "associated_person_count": len(riders),
                },
            }
        )
    return events
