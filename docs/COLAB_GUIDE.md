# Google Colab Execution Guide for Vision Benchmarks

This guide provides step-by-step instructions for running the heavy GPU bake-off and contiguous holdout fine-tuning pipelines on Google Colab.

---

## 1. Architectural Protocol & Truth Hierarchy

In accordance with project engineering invariants:
1. **Cloud GPU Execution**: Runs forward passes on Colab GPU with `--save-raw`, recording candidate predictions ($\text{conf} \ge 0.001$) and execution telemetry (`run_meta.json`). Cloud notebooks do **not** calculate final metrics or synthesize comparison tables.
2. **Local Deterministic Ingestion**: Raw prediction files are ingested into `docs/results/raw/`. The local workstation runs `scripts/compute_tables.py` to compute AP50, 1,000-resample bootstrap confidence intervals (seed 42), Precision/Recall at 0.25 and 0.35, and false-positive rates.
3. **Verification Gate**: `scripts/verify_benchmarks.py` strictly parses documentation tables against committed raw outputs at tolerance $0.001$. Any number lacking a committed raw artifact is rejected.

---

## 2. Zero-Shot Model Bake-Off (`vision/bakeoff_colab.ipynb`)

### Prerequisites & Setup
- **Colab Runtime**: Navigate to **Runtime > Change runtime type**, select **T4 GPU** (or V100/A100), and connect.
- **Estimated Wall-Clock Time**: $\approx 15–20$ minutes total.

### Execution Sequence
1. **Cell 1 (`nvidia-smi`)**: Confirm CUDA GPU device is allocated.
2. **Cell 2 (Dependencies)**: Installs `ultralytics`, `sahi`, `albumentations`, `opencv-python`.
3. **Cell 3 (Clone)**: Clones repo and checks out branch `feat/accuracy-v2`.
4. **Cell 4 (Frame Check)**: Verifies 155 frames in `vision/eval/images/`. If missing or incomplete, runs `sample_frames()` from `vision/source/drone_feed.mp4` (stride 13, offset 6).
5. **Cell 5 (Gate Check)**: Validates `vision/eval/labels/VERIFIED` cryptographic checksum (`a7fb1542fdb1e911299bb73971abc3abeea4aed675ef2a172933a4b168f595fc`).
6. **Cell 6 (Zero-Shot Matrix)**: Sequentially executes 16 configurations across models (`yolov8n/s/m`, `yolo11n/s/m`) and resolutions (`640`, `960`, `1280`), dumping `predictions.json` and `run_meta.json` into `docs/results/raw/<run_id>/`.
7. **Cell 7 (SAHI Evaluation)**: Runs Sliced Aided Hyper Inference (`yolov8s` with 640×640 slices, 0.2 overlap), dumping raw candidates to `docs/results/raw/sahi_yolov8s_640px_all/`.
8. **Cell 8 (Artifact Packaging)**: Zips all raw folders into `colab_bakeoff_raw.zip` and triggers automatic browser download.

---

## 3. Contiguous Holdout Fine-Tuning (`vision/train_colab.ipynb`)

### Prerequisites & Setup
- **Colab Runtime**: T4 GPU or higher.
- **Google Drive**: At least 500 MB free space for checkpointed model weights (`best.pt`).
- **Estimated Wall-Clock Time**:
  - Fold 1 (50 epochs @ 1280px): $\approx 25–35$ minutes
  - Fold 2 (50 epochs @ 1280px): $\approx 25–35$ minutes
  - Holdout Inferences (4 runs): $\approx 3–4$ minutes

### Execution Sequence
1. **Cell 1–4 (Environment & Gate)**: Verifies GPU, installs packages, clones repo on `feat/accuracy-v2`, and verifies cryptographic label gate.
2. **Cell 5 (CPU Smoke Test)**: Runs a 1-epoch, 2-image sanity run on CPU to guarantee training scripts execute without syntax or dependency errors.
3. **Cell 6 (Drive Mount)**: Mounts Google Drive at `/content/drive/MyDrive/aegis_checkpoints` to persist weights against disconnections.
4. **Cell 7 (Train Fold 1)**: Partitions Fold 1 (Train: `0..107`, Purge: `108..112`, Holdout: `113..154`). Trains `yolov8s.pt` for 50 epochs at 1280px with mosaic and mixup augmentations. Copies `best.pt` to Drive.
5. **Cell 8 (Train Fold 2)**: Partitions Fold 2 (Holdout: `0..41`, Purge: `42..46`, Train: `47..154`). Trains `yolov8s.pt` for 50 epochs at 1280px. Copies `best.pt` to Drive.
6. **Cell 9 (Holdout Inferences)**: Runs inference with `--save-raw` for all 4 conditions:
   - Fold 1 Pretrained Baseline (`yolov8s_1280px_val_fold1_baseline`)
   - Fold 1 Fine-Tuned (`yolov8s_1280px_val_fold1_finetuned`)
   - Fold 2 Pretrained Baseline (`yolov8s_1280px_val_fold2_baseline`)
   - Fold 2 Fine-Tuned (`yolov8s_1280px_val_fold2_finetuned`)
7. **Cell 10 (Artifact Packaging)**: Packages raw predictions and trained weights into `colab_train_raw.zip` and triggers browser download.

---

## 4. Local Ingestion & Deterministic Metric Recomputation

Once download completes, ingest the raw outputs into the repository on your local machine:

```bash
# 1. Unpack downloaded zip files into docs/results/raw/
unzip -o colab_bakeoff_raw.zip -d docs/results/
unzip -o colab_train_raw.zip -d docs/results/

# 2. Recompute all metrics, CIs, and markdown tables deterministically
python3 scripts/compute_tables.py

# 3. Verify documentation against the raw prediction records
python3 scripts/verify_benchmarks.py
```

`scripts/verify_benchmarks.py` enforces tolerance $0.001$. Any discrepancy or missing raw file will raise an error and halt verification.
