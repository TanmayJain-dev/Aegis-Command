# Aegis Command - Ground Truth Labeling Protocol

This document provides the standard operating procedure for human verification and curation of the 155-frame tactical drone evaluation dataset (`vision/eval/images/`).

All raw draft predictions have been pre-converted into X-AnyLabeling JSON format in `local_assets/labeling/` with corresponding `classes.txt`. Follow this protocol to review, correct, and certify the ground-truth dataset.

---

## 1. Environment & Setup

We use **X-AnyLabeling** running locally in an isolated CPU environment (`local_assets/labeling_env`).

### Launching the Annotation Tool
From the repository root, launch the application:
```bash
local_assets/labeling_env/bin/xanylabeling
```

### Loading the Dataset
1. In the top toolbar, click **Open Dir** (or press `Ctrl+U`).
2. Select the directory:
   ```
   local_assets/labeling/
   ```
3. Ensure **Auto Save** is toggled ON in the top menu (`File` $\rightarrow$ `Save Automatically`).
4. The 155 images and their pre-labeled draft shapes will load automatically along with predefined classes: `person`, `car`, `truck`, `bus`.

---

## 2. Target Class Definitions

The evaluation dataset focuses strictly on 4 tactical classes:

| Class ID | Name | Definition & Examples | Boundary Invariant |
|---|---|---|---|
| `0` | **person** | Personnel, guards, civilians on foot, workers. | Full body head-to-toe; exclude shadows. |
| `1` | **car** | Sedans, hatchbacks, SUVs, passenger motorcars. | Tight bumper-to-bumper, tire-to-roof. |
| `2` | **truck** | Heavy cargo vehicles, pickups, flatbeds, tactical transport. | Include cargo bed/cab; exclude trailers if separate. |
| `3` | **bus** | Passenger coaches, shuttle vans, minibuses. | Full vehicle envelope. |

> [!IMPORTANT]
> **Do not annotate out-of-scope classes**: Ignore bicycles, motorcycles, fences, light poles, trees, static infrastructure, and animals.

---

## 3. Keyboard Shortcuts Reference

These shortcuts are verified against the active X-AnyLabeling configuration:

| Category | Shortcut | Action |
|---|---|---|
| **Navigation** | `D` | Next image (advances sequence) |
| **Navigation** | `A` | Previous image |
| **Editing** | `R` | Create rectangle annotation box |
| **Editing** | `Ctrl + J` | Selection / Edit Mode (click box to resize/move) |
| **Editing** | `Ctrl + E` | Edit label name / class assignment |
| **Editing** | `Delete` | Delete selected bounding box |
| **Editing** | `Ctrl + Z` | Undo last operation |
| **Zoom & View** | `Ctrl + +` / `Ctrl + =` | Zoom In |
| **Zoom & View** | `Ctrl + -` | Zoom Out |
| **Zoom & View** | `Ctrl + 0` | Reset zoom to original 100% scale |
| **Zoom & View** | `Ctrl + F` | Fit image to window |
| **Zoom & View** | `Ctrl + H` | Toggle annotations visibility (hide/show) |
| **File** | `Ctrl + S` | Save current annotation JSON |

---

## 4. Two-Pass Verification Protocol

Due to high drone camera elevation, people appear small (often 15–40 px tall). Annotators must follow this two-pass review protocol per frame:

### Pass 1: Global Verification & Correction (Fit to Window, `Ctrl+F`)
1. **Fix Boundaries**: Click any pre-labeled box that is too loose or misaligned. Tighten edges to visible pixels. Do not include ground shadow.
2. **Correct Misclassifications**: If a pickup or cargo truck was pre-labeled as `car`, press `Ctrl+E` and select `truck`.
3. **Remove False Positives**: If road markings, trash bins, or HVAC units are detected as people or vehicles, press `Delete`.

### Pass 2: High-Zoom Quadrant Sweep (`Ctrl++` to $\ge 2\times$)
1. Zoom in to $200\%$ magnification.
2. Systematically pan across the four quadrants:
   - **Top-Left** $\rightarrow$ **Top-Right** $\rightarrow$ **Bottom-Left** $\rightarrow$ **Bottom-Right**
3. Locate small, distant, or partially occluded targets missed by the draft model.
4. Press `R` to draw a tight rectangle around missed objects and select the appropriate class label.
5. **Occlusion rule**: Annotate only if $\ge 30\%$ of the body or vehicle chassis is visible.

---

## 5. Pilot Workflow (First 10 Frames)

Before completing the full sequence, run a pilot test on the first 10 frames:

1. Label `frame_000006.jpg` through `frame_000123.jpg` (frames 1–10).
2. Save progress (`Ctrl+S`).
3. In a terminal, run the validation tool in pilot mode:
   ```bash
   vision/.venv/bin/python vision/eval/finalize_labels.py --input local_assets/labeling --output local_assets/pilot_labels
   ```
4. Generate a preview contact sheet to inspect box alignments:
   ```bash
   vision/.venv/bin/python vision/eval/preview_labels.py --labels local_assets/pilot_labels --output local_assets/pilot_preview.jpg --num-frames 10
   ```
5. Check `local_assets/pilot_preview.jpg` to verify box colors, boundary tightness, and class consistency.
6. Once satisfied, proceed with the remaining 145 frames.

---

## 6. Dataset Finalization & Certification Gate

Once all 155 frames have been reviewed and saved in `local_assets/labeling/`:

### Step 1: Run Finalization and Validation Gate
Run `finalize_labels.py` with your full name:
```bash
vision/.venv/bin/python vision/eval/finalize_labels.py --annotator "Firstname Lastname"
```

The script will:
1. Convert all 155 X-AnyLabeling JSON files to standard YOLO format in `vision/eval/labels/`.
2. Execute strict schema and geometric validation checks:
   - Exactly 155 label files present.
   - Exactly 5 tokens per line (`class_id x_center y_center width height`).
   - Class IDs strictly within `{0, 1, 2, 3}`.
   - Coordinates normalized within `[0.0, 1.0]`.
   - Positive dimensions (`width > 0`, `height > 0`).
   - Zero duplicate lines per frame.
   - Warnings logged for boxes $< 6\text{ px}$.
3. Print a comparative distribution table (`Draft` vs `Verified`).
4. Generate the cryptographic and audit marker at:
   ```
   vision/eval/labels/VERIFIED
   ```

### Step 2: Generate Final Contact Sheet Preview
Generate the 12-frame contact sheet to verify the finalized dataset visually:
```bash
vision/.venv/bin/python vision/eval/preview_labels.py
```
This updates `local_assets/label_preview.jpg` with verified ground-truth overlays.

### Step 3: Run Detection Evaluation
With `vision/eval/labels/VERIFIED` in place, run the official evaluation benchmark:
```bash
vision/.venv/bin/python vision/eval/eval_detection.py
```
The benchmark will compute true precision, recall, F1, and mAP@50 metrics against human ground truth.
