# TriNetra Local Vision Service

This service runs the real models in `../models/` locally. It is the non-demo upload inference boundary used by the existing web app at `POST http://127.0.0.1:8010/api/vision/analyze`.

## Windows CPU Setup

From the repository root, run in a PowerShell terminal:

```powershell
.\python-service\setup.ps1
.\python-service\run.ps1
```

Setup creates an isolated `python-service/.venv`, installs CPU-only PyTorch and the Python dependencies, and does not change the machine's global Python/PyTorch or attempt CUDA setup. First-time setup needs internet access. Keep this service running while using video uploads. The web app may set `VITE_VISION_API_URL` to override the default local URL.

## Video Processing

The API decodes the complete video using OpenCV and runs inference on every `analysis.frame_stride`-th decoded frame. Each analyzed frame uses YOLOv8 COCO detection/tracking, the helmet checkpoint, and FastALPR's license-plate detector/OCR. The response includes source frame index, `frame_index / fps` timestamp, dimensions, class/confidence/bounding box, tracking ID when assigned, and plate/OCR output. Only rule-confirmed events contain an evidence JPEG data URL. The browser stores those with the existing evidence/incident records.

The CPU-only configuration is intentional. The local service will not claim GPU execution. Model or dependency failures return an API error; non-demo uploads do not fall back to cached incidents or a fabricated violation.

## Rule Evidence

- Helmetless riding: a model `Without Helmet` detection must overlap a YOLO-tracked person, and that person must be spatially associated with a tracked motorcycle. The detector is the downloaded helmet checkpoint; the association is geometric and can fail with crowded/occluded riders.
- Triple riding: at least three distinct tracked YOLO `person` detections must be associated with the same tracked motorcycle in the same analyzed frame. This is a rule based on detector/tracker evidence, not a dedicated passenger-count model.
- Wrong lane: requires a configured normalized lane polygon and its expected direction. The current rule flags a tracked vehicle inside that polygon moving against the configured direction; it does not infer arbitrary lane markings.
- Signal jumping: requires a normalized traffic-light region and stop-line segment. A COCO `traffic light` detection must be in the configured region, the region must pass the red-pixel ratio, and a tracked vehicle must cross the configured line between analyzed frames while that state is red. Amber/green state and signal timing are not inferred.
- Overspeeding: requires a calibrated 3x3 image-to-ground-plane homography and `speed_limit_kmh`. The tracked vehicle bottom-center is projected to meters; distance between projected points is divided by the elapsed frame-timestamp interval and multiplied by 3.6. With missing calibration or limit, no speed/overspeed incident is emitted.

## Camera Configuration

Edit `config/traffic_rules.json` and restart the service after calibrating a camera. Coordinates for lane polygons, light regions, and stop lines are normalized to image width/height (`0` through `1`). No geometry or speed limit is enabled by default.

A camera entry has this shape; replace every placeholder with measured camera-specific values before enabling the corresponding rule:

```json
{
  "cameras": {
    "CAM-001": {
      "lanes": [
        {
          "id": "lane-name",
          "polygon": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],
          "expected_direction": [dx, dy]
        }
      ],
      "traffic_light_region": [[x1, y1], [x2, y2], [x3, y3]],
      "stop_line": [[x1, y1], [x2, y2]],
      "speed_limit_kmh": 30,
      "speed_homography": [[h11, h12, h13], [h21, h22, h23], [h31, h32, h33]]
    }
  }
}
```

The matrix must transform source-image pixel coordinates into ground-plane meters and must be computed from known corresponding points for that camera. The example limit is illustrative only; it is not active configuration. Do not use it without replacing it with the actual legal limit and calibration. Wrong-lane, red-light, and overspeeding stay disabled until their required fields are present.

Global sampling and confidence settings are in `config/traffic_rules.json`. `frame_stride` trades processing time for temporal detail; crossing and brief events can be missed if set too high. The default upload cap is 500 MiB and can be changed with `TRINETRA_MAX_UPLOAD_BYTES`.

## Test

With the service dependencies installed, from `python-service/` run:

```powershell
python -m unittest discover -s tests -v
```

Those tests feed explicit geometric fixtures into the rule modules; they do not represent AI detections. Validate model precision, camera calibration, and plate OCR on actual target-camera videos before operational use.
