# Aegis Command - Task 1 Cross-Validation Protocol Audit

## 1. Audit of the Previous CV Protocol & Holdout Snooping

### 1.1 Where `split_dataset.py` Writes Validation Frames
In `vision/eval/split_dataset.py` (lines 170–183), the dataset partitioner populates `vision/data/images/val` and `vision/data/labels/val` with symlinks pointing to the holdout fold frames:

```python
    # Populate val
    for s in val_stems:
        img_src = IMAGES_DIR / f"{s}.jpg"
        lbl_src = LABELS_DIR / f"{s}.txt"
        img_dst = DATA_DIR / "images" / "val" / f"{s}.jpg"
        lbl_dst = DATA_DIR / "labels" / "val" / f"{s}.txt"

        if img_src.exists():
            os.symlink(img_src.resolve(), img_dst)
        if lbl_src.exists():
            os.symlink(lbl_src.resolve(), lbl_dst)
        else:
            lbl_dst.touch()
```

Immediately following, `split_dataset.py` (lines 194–206) generates `vision/data/aegis_data.yaml` with the `val` split pointing directly to this directory:

```python
    # Write Ultralytics YAML
    names_yaml = "\n".join([f"  {cid}: {name}" for cid, name in CLASS_MAP.items()])
    yaml_content = f"""# Aegis Command - YOLO Fine-Tuning Dataset Definition (Fold {fold})
path: {DATA_DIR.resolve()}
train: images/train
val: images/val

names:
{names_yaml}
"""
    yaml_path = DATA_DIR / "aegis_data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
```

### 1.2 How Ultralytics Uses `val` to Pick `best.pt`
When invoking `model.train(data="vision/data/aegis_data.yaml", epochs=50, ...)`:
1. At the conclusion of every epoch $e \in \{1, \dots, 50\}$, the Ultralytics training engine (`ultralytics.engine.trainer.BaseTrainer`) invokes `self.validate()`.
2. `self.validate()` loads the images and labels designated by the `val` key in `aegis_data.yaml`—namely, the contiguous holdout fold for that run.
3. Ultralytics computes the validation fitness scalar:
   $$\text{fitness} = 0.1 \times \text{mAP}_{50} + 0.9 \times \text{mAP}_{50\text{--}95}$$
4. If $\text{fitness}_e > \text{fitness}_{\text{best}}$, the trainer updates `fitness_best = fitness_e` and copies the model checkpoint to `weights/best.pt`:
   ```python
   # ultralytics/engine/trainer.py
   if self.fitness > self.best_fitness:
       self.best_fitness = self.fitness
       if self.save:
           self.save_model()
           # saves weights/best.pt
   ```

### 1.3 Why Evaluating `best.pt` on the Holdout Fold Inflates Reported Accuracy
Evaluating `best.pt` on the same holdout validation fold used for model selection is a textbook form of **validation set snooping** (selection bias / "winner's curse"):
- Across 50 epochs of stochastic gradient descent with data augmentations (mosaic, mixup, affine jitter), validation fitness fluctuates due to both genuine feature representations and stochastic alignment with the specific 31 frames of that fold.
- Selecting `best.pt` by taking the $\text{argmax}_{e} \text{fitness}_e(\text{val})$ tunes the hyperparameter (epoch stopping index) directly on the test metric.
- When `eval_detection.py` subsequently runs on `val` using `best.pt`, it does not measure out-of-sample generalization; it measures the peak of a 50-hypothesis search over that exact fold.
- In CV reporting, this systematically biases reported mAP upward and underestimates true generalization variance.

---

## 2. Fixed-Epoch Protocol (`val=False`, `last.pt` Headline)

To eliminate holdout snooping without requiring a 3-way split (train / val / test) on an ultra-compact 155-frame tactical dataset, we enforce a strict **fixed-epoch protocol**:
1. `model.train()` is invoked with `val=False`:
   ```python
   model.train(
       data="vision/data/aegis_data.yaml",
       epochs=50,
       val=False,  # Disables validation during training; zero holdout frames seen
       save=True,
       plots=False
   )
   ```
2. The trainer never loads, evaluates, or computes metrics on `images/val` during the training loop.
3. No checkpoint selection or early stopping is performed. The weights at the completion of epoch 50 (`last.pt`) are frozen.
4. `eval_detection.py` evaluates `last.pt` on the holdout fold for the very first time. Because `last.pt` was chosen a priori based solely on the fixed 50-epoch schedule, the evaluation is completely uncontaminated by selection bias.
5. All headline CV metrics reported in documentation, README, and frontend badges are designated from `last.pt`.

---

## 3. Mathematical Explanation of mAP50 Discrepancy (0.891 vs 0.821 on Fold 3)

### 3.1 Observed Discrepancy
On Fold 3 fine-tuned model evaluation:
- Ultralytics `val` / dense sweep reported: **$\text{mAP}_{50} = 0.891$** (specifically `0.8908` for person AP50).
- `eval_detection.py` at `conf=0.25` reported: **$\text{mAP}_{50} = 0.821$** (specifically `0.8210` for person AP50).

### 3.2 Root Cause Analysis: Candidate Threshold Filtering vs Continuous PR Integration
The Average Precision (AP) under the PASCAL/COCO convention is the area under the precision-recall curve $p(r)$:
$$\text{AP} = \int_{0}^{1} p(r) \, dr$$

In standard object detection evaluation (Ultralytics, COCO API):
- The model outputs all candidate detections down to a very low threshold ($\text{conf} = 0.001$).
- Detections are sorted globally in descending order of confidence.
- Cumulative true positives $\text{TP}(k)$ and false positives $\text{FP}(k)$ are computed as candidates are accepted, tracing recall $r(k) = \frac{\text{TP}(k)}{N_{\text{GT}}}$ from 0 up to maximum reachable recall $R_{\max}$.
- In Fold 3, allowing detections down to $\text{conf} = 0.001$ yields $R_{\max} = 0.9563$ (95.63% recall).
- Continuous or 101-point interpolation across this curve yields:
  $$\text{AP}_{50} = \sum_{i} (r_{i+1} - r_i) \max_{\tilde{r} \ge r_{i+1}} p(\tilde{r}) = 0.8908 \approx 0.891$$

In `eval_detection.py` (lines 266–270):
```python
    for c_thresh in conf_thresholds:  # [0.25, 0.35]
        preds_thresh = [p for p in raw_predictions if p["conf"] >= c_thresh]
        class_eval = {}
        for c_id, c_name in CLASS_NAMES.items():
            m = calculate_metrics_for_class(preds_thresh, ground_truths, target_class=c_id)
```
- Detections were pre-filtered by `p["conf"] >= 0.25` before being passed into `calculate_metrics_for_class`.
- Any true target detected by the model with confidence $0.001 \le \text{conf} < 0.25$ was discarded before precision-recall calculation.
- Consequently, the maximum recall attainable by `preds_thresh` was truncated at the operational point $\text{conf} = 0.25$, which is exactly $R_{0.25} = 0.8415$ (84.15% recall).
- For all $r > 0.8415$, there are zero predictions remaining in `preds_thresh`, causing precision to drop to $0.0$.
- In `compute_ap()` (`vision/eval/metrics.py`, line 41):
  ```python
  mrec = np.concatenate(([0.0], recalls, [1.0]))
  mpre = np.concatenate(([0.0], precisions, [0.0]))
  ```
- Because no predictions exist between $r = 0.8415$ and $r = 1.0$, the integral over $[0.8415, 1.0]$ contributes $0.0$:
  $$\text{AP}_{\text{truncated}} = \int_{0}^{0.8415} p(r) \, dr + \int_{0.8415}^{1.0} 0 \, dr = 0.8210$$
- The loss of the tail area $[0.8415, 0.9563]$ where precision remains moderate accounts for the exact difference:
  $$\Delta \text{AP} = 0.8908 - 0.8210 = 0.0698 \approx 0.070$$

### 3.3 Summary Matrix

| Evaluation Approach | Min Conf | Max Recall ($R_{\max}$) | Tail Area $[0.84, 0.96]$ | Person $\text{AP}_{50}$ | Metric Role |
|:---|:---:|:---:|:---:|:---:|:---|
| **Dense Sweep (Ultralytics / Standard)** | $0.001$ | $0.9563$ | Included | **$0.891$** | Standard benchmark capacity |
| **Operational Threshold (`eval_detection.py`)** | $0.250$ | $0.8415$ | Truncated to $0$ | **$0.821$** | Real-world deployment metric |

Both numbers are mathematically correct under their respective definitions; the discrepancy is entirely explained by candidate pre-filtering at $\text{conf}=0.25$ versus standard continuous curve integration down to $\text{conf}=0.001$.
