# Aegis Command - Detection & Tracking Schema Specification

This document defines the schema contracts for optical detections, tracking trajectories, and telemetry feeds in Aegis Command.

---

## Schema v2 Specification (Trajectorial Representation)

Schema v2 organizes detection data by **track trajectory** rather than per-frame buckets. This reduces JSON payload size, enables client-side keyframe interpolation, and maintains strict metadata provenance for hardware/extractor auditing.

### Top-Level Structure

```json
{
  "schema": 2,
  "meta": {
    "feed_id": "uav-alpha",
    "width": 1920,
    "height": 1080,
    "fps": 59.94,
    "duration_s": 33.6,
    "stride": 1,
    "model": "yolov8s.pt",
    "imgsz": 640,
    "tracker": "bytetrack",
    "generated_at": "2026-10-11T08:00:00Z",
    "git_commit": "62de537",
    "speed_is_simulated": true,
    "heading_frame": "image"
  },
  "tracks": [
    {
      "id": "person-3",
      "cls": "person",
      "t": [0.10, 0.15, 0.20, 0.25],
      "box": [
        [1838, 334, 1868, 388],
        [1839, 335, 1869, 389],
        [1840, 336, 1870, 390],
        [1841, 337, 1871, 391]
      ],
      "conf": [0.82, 0.85, 0.84, 0.86],
      "spd_kmh": [0.0, 1.2, 1.4, 1.1],
      "dir": ["-", "NW", "NW", "NW"]
    }
  ]
}
```

### Field Definitions

#### Metadata (`meta`)

| Field | Type | Description |
|---|---|---|
| `feed_id` | `string` | Unique identifier matching `feeds/index.json` (e.g., `"uav-alpha"`). |
| `width` | `number` (int) | Source footage horizontal pixel resolution (e.g., `1920`). |
| `height` | `number` (int) | Source footage vertical pixel resolution (e.g., `1080`). |
| `fps` | `number` (float) | Source video frame rate (e.g., `59.94`). |
| `duration_s` | `number` (float) | Total media playback duration in seconds. |
| `stride` | `number` (int) | Frame extraction stride during detection inference (e.g., `1` for continuous tracking). |
| `model` | `string` | Model weights identifier used (e.g., `"yolov8s.pt"`). |
| `imgsz` | `number` (int) | Inference image dimension (e.g., `640` or `960`). |
| `tracker` | `string` | Multi-object tracking algorithm (e.g., `"bytetrack"` or `"botsort"`). |
| `generated_at` | `string` (ISO-8601) | Timestamp of extractor execution. |
| `git_commit` | `string` | Commit hash of repository when data was extracted. |
| `speed_is_simulated` | `boolean` | **Must be `true`** for mock/simulated kinematic estimates. Raw pixel trackers do not measure true ground speed. |
| `heading_frame` | `string` | Coordinate frame for direction (`"image"` or `"geographic"`). |

#### Track Object (`tracks[]`)

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Persistent identifier across keyframes (e.g., `"person-3"`). |
| `cls` | `string` | Target classification (`"person"`, `"car"`, `"truck"`, `"bus"`). |
| `t` | `number[]` | Ascending timestamp array in floating-point seconds (e.g. `[0.10, 0.15, ...]`). In memory, loaded as `Float64Array`. |
| `box` | `[number, number, number, number][]` | Bounding boxes formatted as `[x1, y1, x2, y2]` in **source resolution pixels** (0 to `meta.width`, 0 to `meta.height`). |
| `conf` | `number[]` | Detection confidence scores ($0.0 \le c \le 1.0$) corresponding 1-to-1 with keyframes in `t`. |
| `spd_kmh` | `number[]` (optional) | Kinematic speed estimate per keyframe. Simulated attribute. |
| `dir` | `string[]` (optional) | Heading or travel direction string per keyframe (`"N"`, `"NW"`, `"-"`, etc.). |

---

## Client Sampling & Interpolation Rules

1. **Numeric Arrays Only**: All timestamps in memory MUST be stored as `Float64Array`. Never execute `parseFloat()` during render or animation frames.
2. **Binary Search**: Keyframe lookups must execute via binary search ($O(\log N)$) on `Float64Array`.
3. **Linear Interpolation**:
   - For query time $t$ where $t_i \le t \le t_{i+1}$ within a track's keyframes:
     $$\alpha = \frac{t - t_i}{t_{i+1} - t_i}$$
     $$\text{box}[j] = \text{box}_i[j] + \alpha \cdot (\text{box}_{i+1}[j] - \text{box}_i[j])$$
   - Confidence: $\text{conf} = (1 - \alpha) \cdot \text{conf}_i + \alpha \cdot \text{conf}_{i+1}$
   - Kinematics: $\text{spd} = (1 - \alpha) \cdot \text{spd}_i + \alpha \cdot \text{spd}_{i+1}$
   - Direction: $\text{dir} = \text{dir}_i \text{ if } \alpha < 0.5 \text{ else } \text{dir}_{i+1}$
4. **No Extrapolation**: Never extrapolate coordinates prior to the first keyframe $t_0$ or after the final keyframe $t_k$. If $t < t_0$ or $t > t_k$, the track is inactive.
5. **Resolution-Decoupled Scaling**:
   - Web video can be transcoded (e.g. to 720p or 540p) to conserve bandwidth.
   - Canvas coordinate scaling MUST be calculated against `meta.width` and `meta.height`, **never** `video.videoWidth` or `video.videoHeight`:
     $$\text{scaleX} = \frac{\text{canvas.width}}{\text{meta.width}}, \quad \text{scaleY} = \frac{\text{canvas.height}}{\text{meta.height}}$$

---

## Schema v1 Compatibility & Client-Side Bridging Pipeline

The frontend maintains backward compatibility for legacy and intermediate `detections.json` files formatted under Schema v1.

### Keyframe Sampling & Client-Side Bridging

All active surveillance feeds (`uav-alpha`, `cctv-bravo`, and `bodycam-charlie`) currently ship under Schema v1 with keyframes every 0.5s, bridged client-side by class+IoU matching with linear interpolation (`imgsz=1280`, conf=0.35, ByteTrack). Compact JSON serialization is enforced to maintain lean bundle footprints (< 500 KB per feed timeline).

### Structure
```json
{
  "meta": {
    "feed_id": "uav-alpha",
    "evaluated": true,
    "model": "aegis_demo_full_last.pt",
    "generator_commit": "be1308e...",
    "weights_sha256": "93761a11...",
    "detections_sha256": "..."
  },
  "0.0": [
    {
      "id": "Vehicle-1",
      "class": "person",
      "confidence": 0.43,
      "box": [1838.4, 334.1, 1868.3, 388.2],
      "speed_kmh": 0,
      "direction": "-"
    }
  ]
}
```

### Client-Side Bridging & Interpolation

To eliminate optical overlay stutter and flicker between discrete keyframes without inflating tracking errors, `frontend/src/lib/timeline.ts` (`createV1Timeline`) executes client-side bridging at feed load time:

1. **Greedy Matching**:
   - Consecutive keyframes at $t_i$ and $t_{i+1}$ are matched when the sampling gap $\Delta t = t_{i+1} - t_i \le \text{MAX\_BRIDGE\_S}$ ($1.0\text{ s}$).
   - Box association uses greedy bipartite matching based on:
     $$\text{class}_A = \text{class}_B \quad \text{AND} \quad \left(\text{IoU}(A, B) \ge 0.05 \;\lor\; \text{dist}(\text{center}_A, \text{center}_B) \le 1.5 \times \max(w_A, h_A)\right)$$
   - Box matching operates independent of persistent tracking IDs, guaranteeing continuity despite tracker ID churn across frame gaps.

2. **Playback Sampling (`sampleAt(t)`)**:
   - For query time $t$ between matched keyframes $t_i \le t \le t_{i+1}$ ($\Delta t \le 1.0\text{ s}$):
     - **Matched Pairs**: Bounding box coordinates are linearly interpolated with $\alpha = \frac{t - t_i}{t_{i+1} - t_i}$. Kinematics and confidence are inherited from the chronologically nearer sample, and the box is flagged with `interpolated: true`.
     - **Unmatched Boxes**: Rendered only when $|t - t_{\text{sample}}| \le 0.15\text{ s}$. Unmatched detections are suppressed beyond $0.15\text{ s}$ to prevent stale phantom boxes from lingering in the viewport.
   - For sampling gaps $\Delta t > 1.0\text{ s}$, the timeline falls back to the legacy tolerance window ($0.05\text{ s}$) around each sample.

### Secondary Feeds Status (`cctv-bravo`, `bodycam-charlie`)

- **Video Assets**: Standardized 720p 30fps web video copies (`frontend/public/feeds/*/video.mp4`) ship directly in the repository (< 8 MB each).
- **Inference & Evaluation**: Detection timelines for secondary feeds are generated using zero-shot inference (`yolov8m.pt` @ 1280px with keyframes every 0.5s, bridged client-side by class+IoU matching with linear interpolation).
- **Evaluation Status**: Both secondary feeds are explicitly configured in metadata with `"evaluated": false`. Human-verified ground-truth bounding box annotations and cross-validation benchmark statistics exist exclusively for `uav-alpha`. Secondary feeds render a visible operational warning badge in the dashboard.


