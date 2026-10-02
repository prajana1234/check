from math import hypot

from inference.detections import Detection


def point_in_bbox(point: tuple[float, float], bbox: tuple[float, float, float, float]) -> bool:
    x, y = point
    x1, y1, x2, y2 = bbox
    return x1 <= x <= x2 and y1 <= y <= y2


def associate_person_to_motorcycle(
    person: Detection,
    motorcycles: list[Detection],
    frame_width: int,
    frame_height: int,
) -> Detection | None:
    px, py = person.center
    person_width = max(1.0, person.bbox[2] - person.bbox[0])
    person_height = max(1.0, person.bbox[3] - person.bbox[1])
    candidates: list[tuple[float, Detection]] = []
    for motorcycle in motorcycles:
        x1, y1, x2, y2 = motorcycle.bbox
        bike_width = max(1.0, x2 - x1)
        horizontal = max(x1 - px, 0.0, px - x2)
        vertical_gap = max(y1 - person.bbox[3], 0.0, person.bbox[1] - y2)
        if horizontal > max(bike_width, person_width) * 1.25:
            continue
        if vertical_gap > person_height * 0.75:
            continue
        distance = hypot(horizontal / max(frame_width, 1), vertical_gap / max(frame_height, 1))
        candidates.append((distance, motorcycle))
    return min(candidates, key=lambda candidate: candidate[0])[1] if candidates else None


def polygon_contains(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    inside = False
    x, y = point
    previous_x, previous_y = polygon[-1]
    for current_x, current_y in polygon:
        intersects = ((current_y > y) != (previous_y > y)) and (
            x < (previous_x - current_x) * (y - current_y) / (previous_y - current_y) + current_x
        )
        if intersects:
            inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def signed_line_side(point: tuple[float, float], line: list[list[float]]) -> float:
    (x1, y1), (x2, y2) = line
    return (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)
