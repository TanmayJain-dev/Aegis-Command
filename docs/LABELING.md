# Aegis Command - Ground Truth Labeling Protocol

This document outlines the standard operating procedure for human verification and curation of the evaluation dataset extracted from tactical feeds (`vision/eval/images/`).

---

## 1. Tool Recommendations

We recommend either of the following open-source, local-first annotation suites:

1. **X-AnyLabeling (Recommended)**:
   - Local desktop application (Linux, macOS, Windows).
   - Direct support for YOLO `.txt` format and Auto-Labeling refinement.
   - GitHub: [CVHub520/X-AnyLabeling](https://github.com/CVHub520/X-AnyLabeling)
2. **CVAT (Computer Vision Annotation Tool)**:
   - Web-based, containerized, supports video interpolation and YOLO 1.1 format.
   - Run locally via Docker: `docker run -p 8080:8080 openvino/cvat_server`

---

## 2. Target Class Definitions

The evaluation dataset focuses strictly on 4 tactical classes:

| Class ID | Name | Definition & Examples |
|---|---|---|
| `0` | **person** | Pedestrians, personnel, security operators, civilians on foot. |
| `1` | **car** | Sedans, hatchbacks, SUVs, passenger motorcars. |
| `2` | **truck** | Heavy cargo vehicles, pickup trucks, flatbeds, tactical transport. |
| `3` | **bus** | Passenger coaches, shuttle vans/minibuses. |

> [!NOTE]
> Ignore any other objects (e.g. bicycles, motorcycles, street furniture, animals, trees).

---

## 3. Bounding-Box Annotation Rules

1. **Tight Boundary**:
   - The bounding box must tightly enclose all visible pixels of the object.
   - Do not include shadows, reflections, or projected light beams.
2. **Occlusion Handling**:
   - If an object is partially occluded by fencing, foliage, or other vehicles, annotate it **only if $\ge 30\%$ of the object is visible**.
   - If $< 30\%$ is visible, do not annotate.
3. **Truncation at Image Edges**:
   - If an object is cut off at the edge of the frame, draw the box up to the frame boundary.
4. **Consistency Across Keyframes**:
   - Maintain class classification across temporal observations.

---

## 4. Verification Workflow

1. **Load Data**:
   - Point your annotation tool to images in `vision/eval/images/`.
   - Import initial draft annotations from `vision/eval/labels_draft/`.
2. **Review & Correct**:
   - Review each of the 155 frames sequentially.
   - Correct box boundaries, fix misclassifications, and remove false positives.
   - Add any missed ground-truth instances.
3. **Export Verified Labels**:
   - Export annotations in standard YOLO format: `<class_id> <x_center> <y_center> <width> <height>` (normalized to `[0, 1]`).
   - Save the verified `.txt` files directly into:
     ```
     vision/eval/labels/
     ```
   - **Do NOT overwrite `vision/eval/labels_draft/`**; draft labels must remain as the baseline reference.

---

## 5. Certification Gate (`VERIFIED` Marker File)

The automated evaluation runner (`vision/eval/eval_detection.py`) **strictly prohibits running evaluation against draft labels**. It will halt immediately unless a valid `VERIFIED` marker exists in `vision/eval/labels/`.

Once human verification of all frames is complete, create:
```
vision/eval/labels/VERIFIED
```

The file must contain:
```
Annotator: <Human Full Name>
Date: <YYYY-MM-DD>
Base Commit: <Git Commit SHA>
Tool Used: <X-AnyLabeling / CVAT>
Frame Count: 155
Verified Status: APPROVED
```
