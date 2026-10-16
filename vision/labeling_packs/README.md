# Aegis Command - Secondary Feeds Labeling Pack (Task 7)

This directory contains human-verification ground truth labeling packs for the secondary surveillance feeds:
- **`cctv-bravo/`**: Perimeter Fixed CCTV Sector 4 (40 evenly spaced frames, 1280x720 @ 25 fps, 28.56s).
- **`bodycam-charlie/`**: Quick Reaction Team (QRT) Forward Patrol Bodycam (40 evenly spaced frames, 1280x720 @ 29.97 fps, 26.86s).

---

## STRICT VERIFICATION INVARIANT: ZERO MODEL PRE-LABELS
> **CRITICAL PROTOCOL REQUIREMENT**:
> Per project truth hierarchy and hackathon evaluation integrity rules:
> - **NO model predictions, YOLO outputs, or automated pseudo-labels are used as ground truth.**
> - All label files (`labels/*.txt`) are initialized completely empty.
> - Every bounding box must be drawn or verified directly by human annotators.
> - The manifest marks `reviewed: false` and `prelabels_used: false` until human certification is complete.

---

## 1. Directory Structure

```text
vision/labeling_packs/
├── README.md                     # This operational protocol guide
├── cctv-bravo/
│   ├── classes.txt               # Class definitions (person, car, truck, motorcycle, bus)
│   ├── manifest.json             # Frame-by-frame metadata (reviewed=false)
│   ├── images/                   # 40 extracted frames (.jpg, quality=95)
│   └── labels/                   # 40 empty YOLO-format ground truth text files (.txt)
└── bodycam-charlie/
    ├── classes.txt               # Class definitions (person, car, truck, motorcycle, bus)
    ├── manifest.json             # Frame-by-frame metadata (reviewed=false)
    ├── images/                   # 40 extracted frames (.jpg, quality=95)
    └── labels/                   # 40 empty YOLO-format ground truth text files (.txt)
```

---

## 2. Target Class Definitions

| Class ID | Class Name | Definition & Examples | Boundary Invariant |
|:---:|:---|:---|:---|
| `0` | **person** | Sentries, guards, patrol officers, civilians on foot | Full head-to-toe envelope. Exclude ground shadow. |
| `1` | **car** | Sedans, SUVs, hatchbacks, civilian light vehicles | Tight chassis boundary tire-to-roof. |
| `2` | **truck** | Heavy transports, flatbeds, pickups, tactical trucks | Include cargo bed/cab. Exclude disconnected trailers. |
| `3` | **motorcycle**| Two-wheelers, motorbikes, scooters, couriers | Vehicle and mounted rider combined as single target. |
| `4` | **bus** | Troop carriers, shuttle vans, minibuses, coaches | Full vehicle envelope bumper-to-bumper. |

---

## 3. Annotation Workflow with X-AnyLabeling

### Step 1: Launch Tool
Run X-AnyLabeling in your Python environment:
```bash
# If installed via pip
xanylabeling

# Or from local labeling environment if configured
local_assets/labeling_env/bin/xanylabeling
```

### Step 2: Open Image Directory
1. Click **Open Dir** (or press `Ctrl+U`).
2. Select `vision/labeling_packs/cctv-bravo/images` (or `bodycam-charlie/images`).
3. Click **Change Output Dir** in the toolbar, and select the corresponding `labels/` directory.
4. Verify that **Save Automatically** is checked under the `File` menu.
5. In the class dropdown, ensure the 5 classes from `classes.txt` are loaded.

### Step 3: Draw Annotations
- Press `R` to activate rectangle creation.
- Click and drag around visible targets matching the 5 classes.
- Assign the appropriate class label (`person`, `car`, `truck`, `motorcycle`, `bus`).
- **Occlusion Threshold**: Annotate only targets where $\ge 30\%$ of the body or vehicle chassis is visible.
- Exclude severe motion blur where boundaries cannot be determined to within $\pm 5$ pixels.

### Step 4: Key Shortcuts
- `D`: Next image
- `A`: Previous image
- `R`: Create rectangle box
- `Ctrl + J`: Edit/move existing box
- `Delete`: Delete selected box
- `Ctrl + S`: Force save
- `Ctrl + +` / `Ctrl + -`: Zoom in / out

---

## 4. Post-Annotation Certification

Once all 40 frames of a feed have been reviewed:
1. Update `manifest.json`:
   - Set `"reviewed": true`
   - Set `"annotator": "Annotator Name"`
   - Set `"verification_date": "YYYY-MM-DDTHH:MM:SSZ"`
2. Compute the cryptographic SHA-256 hash across all label files:
   ```bash
   python3 -c "
   import hashlib, glob
   files = sorted(glob.glob(vision/labeling_packs/cctv-bravo/labels/*.txt))
   hasher = hashlib.sha256()
   for f in files:
       hasher.update(open(f, rb).read())
   print(SHA256:, hasher.hexdigest())
   "
   ```
3. Create `VERIFIED` marker with date and hash before running any evaluation.
