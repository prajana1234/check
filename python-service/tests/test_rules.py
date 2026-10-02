import unittest
from pathlib import Path

import numpy as np

from inference.detections import Detection, FrameDetections, PlateDetection
from inference.trajectory_tracker import TrajectoryTracker
from rules import helmet_rule, overspeed_rule, signal_jump_rule, triple_riding_rule, wrong_lane_rule
from rules.engine import RuleEngine


def detection(
    class_name: str,
    bbox: tuple[float, float, float, float],
    tracking_id: int | None,
    source: str = "yolo",
    confidence: float = 0.9,
) -> Detection:
    return Detection(class_name, confidence, bbox, tracking_id, source)


def frame(
    objects: list[Detection],
    helmets: list[Detection] | None = None,
    image: np.ndarray | None = None,
    plates: list[PlateDetection] | None = None,
) -> FrameDetections:
    return FrameDetections(
        frame_index=3,
        timestamp_seconds=1.0,
        fps=10.0,
        width=100,
        height=100,
        objects=objects,
        helmet_objects=helmets or [],
        plates=plates or [],
        frame=image if image is not None else np.zeros((100, 100, 3), dtype=np.uint8),
    )


class TrafficRuleTests(unittest.TestCase):
    def test_helmet_rule_requires_negative_helmet_and_tracked_rider(self) -> None:
        motorcycle = detection("motorcycle", (30, 55, 70, 90), 12)
        person = detection("person", (35, 20, 60, 60), 4)
        without_helmet = detection("Without Helmet", (42, 30, 52, 40), None, "helmet-yolo")
        results = helmet_rule.evaluate(
            frame([motorcycle, person], [without_helmet]), 0.35, set()
        )
        self.assertEqual([item["violation"] for item in results], ["Helmetless Riding"])
        self.assertEqual(results[0]["tracking_id"], 12)

    def test_helmet_rule_does_not_flag_without_person_or_vehicle(self) -> None:
        without_helmet = detection("Without Helmet", (42, 30, 52, 40), None, "helmet-yolo")
        results = helmet_rule.evaluate(frame([], [without_helmet]), 0.35, set())
        self.assertEqual(results, [])

    def test_triple_riding_requires_three_tracked_people_on_one_motorcycle(self) -> None:
        motorcycle = detection("motorcycle", (30, 55, 70, 90), 12)
        people = [
            detection("person", (35 + offset, 20, 60 + offset, 60), track_id)
            for offset, track_id in ((0, 1), (3, 2), (6, 3))
        ]
        results = triple_riding_rule.evaluate(frame([motorcycle, *people]), 0.35, set())
        self.assertEqual([item["violation"] for item in results], ["Triple Riding"])
        self.assertEqual(results[0]["details"]["associated_person_count"], 3)

    def test_wrong_lane_requires_configured_lane_and_opposite_travel(self) -> None:
        vehicle = detection("car", (35, 40, 45, 50), 8)
        current = frame([vehicle])
        previous = {8: (0.65, 0.5)}
        self.assertEqual(wrong_lane_rule.evaluate(current, {}, previous, 0.35, set()), [])
        lane = {
            "lanes": [
                {
                    "id": "test-lane",
                    "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
                    "expected_direction": [1, 0],
                }
            ]
        }
        results = wrong_lane_rule.evaluate(current, lane, previous, 0.35, set())
        self.assertEqual([item["violation"] for item in results], ["Wrong Lane"])

    def test_signal_jump_requires_red_region_and_crossing(self) -> None:
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        image[10:25, 10:25] = (0, 0, 255)
        light = detection("traffic light", (10, 10, 20, 20), 2)
        vehicle = detection("car", (50, 45, 60, 60), 7)
        config = {
            "traffic_light_region": [[0.05, 0.05], [0.25, 0.05], [0.25, 0.25], [0.05, 0.25]],
            "stop_line": [[0.5, 0.0], [0.5, 1.0]],
        }
        results = signal_jump_rule.evaluate(
            frame([light, vehicle], image=image), config, {7: (0.45, 0.6)}, 0.35, set()
        )
        self.assertEqual([item["violation"] for item in results], ["Signal Jumping"])
        self.assertEqual(
            signal_jump_rule.evaluate(
                frame([light, vehicle]), config, {7: (0.45, 0.6)}, 0.35, set()
            ),
            [],
        )

    def test_speed_uses_calibrated_distance_and_elapsed_time(self) -> None:
        tracker = TrajectoryTracker()
        homography = [[0.01, 0, 0], [0, 0.01, 0], [0, 0, 1]]
        first = detection("car", (0, 0, 10, 10), 5)
        second = detection("car", (100, 0, 110, 10), 5)
        self.assertIsNone(tracker.update([first], 0.0, homography, 0.5)[5])
        speed = tracker.update([second], 1.0, homography, 0.5)[5]
        self.assertAlmostEqual(speed or 0, 3.6, places=2)

        vehicle_frame = frame([second])
        self.assertEqual(overspeed_rule.evaluate(vehicle_frame, {}, {5: speed}, 0.35, set()), [])
        calibrated = {"speed_limit_kmh": 3.5, "speed_homography": homography}
        results = overspeed_rule.evaluate(vehicle_frame, calibrated, {5: speed}, 0.35, set())
        self.assertEqual([item["violation"] for item in results], ["Overspeeding"])
        self.assertEqual(results[0]["speed_limit_kmh"], 3.5)

    def test_rule_engine_attaches_real_frame_evidence_and_plate_details(self) -> None:
        engine = RuleEngine(Path("config/traffic_rules.json"))
        engine.start_video("CAM-001")
        motorcycle = detection("motorcycle", (30, 55, 70, 90), 12)
        person = detection("person", (35, 20, 60, 60), 4)
        without_helmet = detection("Without Helmet", (42, 30, 52, 40), None, "helmet-yolo")
        plate = PlateDetection((40, 65, 50, 72), 0.9, "TEST123", 0.95)
        events = engine.process_frame(
            frame([motorcycle, person], [without_helmet], plates=[plate])
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["camera_id"], "CAM-001")
        self.assertEqual(events[0]["license_plate"], "TEST123")
        self.assertTrue(events[0]["evidence_preview"].startswith("data:image/jpeg;base64,"))
        self.assertIn("helmet_confidence", events[0]["details"])


if __name__ == "__main__":
    unittest.main()
