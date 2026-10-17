# Aegis Command - Secondary Feeds Ground-Truth Labeling Protocol (Task 7)

This document provides the standard operating procedure for annotating and certifying the secondary surveillance feeds: **`cctv-bravo`** (fixed perimeter CCTV) and **`bodycam-charlie`** (mobile tactical bodycam).

---

## 1. Strict Protocol Invariants

> [!CAUTION]
> **ZERO MODEL PRE-LABELS INVARIANT**:
> In accordance with the project's evidence hierarchy, **NO model pre-labels or pseudo-labels are used as ground truth**.
> All 40 frames per feed have been extracted cleanly with empty template labels. Every bounding box must be placed and classified by a human annotator. Using model outputs to bootstrap ground truth introduces systemic confirmation bias and invalidates evaluation benchmarks.

---

## 2. Dataset Packs Overview

Both packs reside under `vision/labeling_packs/`:

| Feed Key | Source Video | Resolution & FPS | Sampled Frames | Directory | Status |
|---|---|---|---|---|---|
| **`cctv-bravo`** | `frontend/public/feeds/cctv-bravo/video.mp4` | 1280×720 @ 25.00 fps | 40 evenly spaced frames | `vision/labeling_packs/cctv-bravo/` | `reviewed: false` |
| **`bodycam-charlie`** | `frontend/public/feeds/bodycam-charlie/video.mp4` | 1280×720 @ 29.97 fps | 40 evenly spaced frames | `vision/labeling_packs/bodycam-charlie/` | `reviewed: false` |

Each pack contains:
- `images/`: 40 high-quality JPEG frames (`{feed}_frame_{i:02d}_{frame_idx:04d}.jpg`).
- `labels/`: 40 corresponding YOLO-format `.txt` files (initially empty).
- `classes.txt`: The 5 product class names in index order.
- `manifest.json`: Machine-readable metadata tracking frame timestamps, resolution, and review status (`reviewed: false`).

---

## 3. Target Class Definitions

Annotations must use the standard 5 product classes:

| Class ID | Class Name | Definition & Examples | Boundary Rules |
|---|---|---|---|
| `0` | **person** | Patrol personnel, civilians, guards, workers. | Full body envelope (head to foot); exclude cast shadows. |
| `1` | **car** | Sedans, hatchbacks, passenger SUVs, police cruisers. | Tight bumper-to-bumper and tire-to-roof box. |
| `2` | **truck** | Cargo trucks, tactical transports, pickups, flatbeds. | Full vehicle envelope including cargo bed; exclude decoupled trailers. |
| `3` | **motorcycle** | Motorcycles, motorbikes, mopeds, scooters. | Include rider and bike together as single entity if mounted. |
| `4` | **bus** | Passenger coaches, shuttle vans, transit buses. | Complete vehicle outer perimeter. |

> [!NOTE]
> Do NOT annotate static infrastructure, trees, light poles, animals, clocks, or bicycles.

---

## 4. X-AnyLabeling Step-by-Step Instructions

We use **X-AnyLabeling** to review and annotate images.

### Step 1: Open the Feed Image Directory
1. Launch X-AnyLabeling.
2. In the top toolbar, click **Open Dir** (or press `Ctrl+U`).
3. Select `vision/labeling_packs/cctv-bravo/images` (or `bodycam-charlie/images`).
4. In the menu, click **Change Output Dir** (`Ctrl+R`) and select the matching `labels/` directory:
   - For `cctv-bravo`: `vision/labeling_packs/cctv-bravo/labels`
   - For `bodycam-charlie`: `vision/labeling_packs/bodycam-charlie/labels`
5. Set label format to **YOLO** in the bottom left dropdown menu.

### Step 2: Annotate Objects
- Press `R` to draw rectangular bounding boxes around all target entities.
- Select the appropriate class from `classes.txt` (`person`, `car`, `truck`, `motorcycle`, `bus`).
- Press `D` to advance to the next frame; press `A` to go back.
- Ensure **Auto Save** is enabled (`File` $\rightarrow$ `Save Automatically`).

### Step 3: Annotation Quality Standards
- **Minimum Box Size**: Entities $< 8\text{ px}$ in height should not be annotated unless distinctly recognizable.
- **Occlusions**: If an entity is $> 70\%$ occluded, do not annotate it.
- **Tight Fit**: Avoid loose borders; bounding box boundaries should touch the outermost visible pixels of the entity.

---

## 5. Certification & Manifest Update

Once all 40 frames for a feed have been labeled:

1. Open `vision/labeling_packs/{feed}/manifest.json`.
2. Update the review header:
   ```json
   {
     "feed": "cctv-bravo",
     "reviewed": true,
     "annotator": "Prachi",
     "verification_date": "2026-10-16"
   }
   ```
3. Run label QA validation to ensure zero formatting errors:
   ```bash
   python3 vision/eval/qa_labels.py
   ```
4. Once verified, the secondary feed can be ingested into evaluation benchmarks and the UI badge will update from `"not evaluated"` to `"evaluated on 40 labelled frames"`.
