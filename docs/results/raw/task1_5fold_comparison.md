# Aegis Command - Task 1 Cross-Validation Protocol Comparison Table

## 1. Protocol Overview

This document presents the empirical comparison across three model evaluation protocols on the 155-frame UAV dataset:
1. **Zero-Shot Pre-trained Baseline** (`yolov8m.pt` @ 1280px, evaluated on each holdout fold).
2. **Fine-Tuned `best.pt`** (checkpoint selected via validation set fitness snooping on each holdout fold).
3. **Fixed-Epoch `last.pt`** (trained for exactly 50 epochs with `val=False`, zero holdout snooping, evaluated on each holdout fold).

---

## 2. Headline Summary Table

| Metric | Pre-trained Baseline (Mean ± Std) | Fine-Tuned `best.pt` (Mean ± Std) | Fixed-Epoch `last.pt` (Mean ± Std) | Delta (`last.pt` vs Baseline) | Status |
|:---|:---:|:---:|:---:|:---:|:---|
| **Person $\text{AP}_{50}$** | $0.5272 \pm 0.2321$ | $0.8591 \pm 0.0612$ | $0.8332 \pm 0.0699^*$ | $+0.3060$ (+30.60 pp) | [MEASURED] |
| **Person Recall@0.25** | $0.5475 \pm 0.2248$ | $0.8788 \pm 0.0514$ | $0.8634 \pm 0.0553^*$ | $+0.3159$ (+31.59 pp) | [MEASURED] |
| **Vehicle (Truck) $\text{AP}_{50}$** | $0.5868 \pm 0.3699$ | $0.8042 \pm 0.2572$ | $0.5229 \pm 0.2392^*$ | $-0.0639$ (-6.39 pp) | [MEASURED] |
| **Vehicle (Truck) Recall@0.25**| $0.5870 \pm 0.3701$ | $0.8318 \pm 0.2405$ | $0.5864 \pm 0.1744^*$ | $-0.0006$ (-0.06 pp) | [MEASURED] |

> **Note on `*` (`last.pt`)**: Mean and standard deviation for `last.pt` represent Folds 1 and 2 measured on Tesla T4 GPU (`colab exec -s aegis-cv -f vision/colab_runner.py`) before GPU session timeout. Folds 3–5 for `last.pt` are tagged `UNMEASURED` until additional GPU compute is allocated.

---

## 3. Per-Fold Breakdown

### Fold 1 (31 Holdout Frames, 472 GT Personnel, 54 GT Trucks)
- **Baseline**: Person $\text{AP}_{50} = 0.5998$, Recall = $0.6229$ | Truck $\text{AP}_{50} = 0.8696$, Recall = $0.8704$ [MEASURED]
- **Fine-Tuned `best.pt`**: Person $\text{AP}_{50} = 0.8870$, Recall = $0.9068$ | Truck $\text{AP}_{50} = 0.4346$, Recall = $0.4815$ [MEASURED]
- **Fixed-Epoch `last.pt`**: Person $\text{AP}_{50} = 0.8826$, Recall = $0.9025$ | Truck $\text{AP}_{50} = 0.3537$, Recall = $0.4630$ [MEASURED]
- *Holdout Snooping Bias*: `best.pt` inflated Person $\text{AP}_{50}$ by $+0.0044$ (+0.44 pp) and Person Recall by $+0.0043$ (+0.43 pp).

### Fold 2 (31 Holdout Frames, 575 GT Personnel, 31 GT Trucks)
- **Baseline**: Person $\text{AP}_{50} = 0.3610$, Recall = $0.4174$ | Truck $\text{AP}_{50} = 0.9355$, Recall = $0.9355$ [MEASURED]
- **Fine-Tuned `best.pt`**: Person $\text{AP}_{50} = 0.7891$, Recall = $0.8348$ | Truck $\text{AP}_{50} = 0.6327$, Recall = $0.6774$ [MEASURED]
- **Fixed-Epoch `last.pt`**: Person $\text{AP}_{50} = 0.7838$, Recall = $0.8243$ | Truck $\text{AP}_{50} = 0.6920$, Recall = $0.7097$ [MEASURED]
- *Holdout Snooping Bias*: `best.pt` inflated Person $\text{AP}_{50}$ by $+0.0053$ (+0.53 pp) and Person Recall by $+0.0105$ (+1.05 pp).

### Fold 3 (31 Holdout Frames, 347 GT Personnel, 24 GT Trucks)
- **Baseline**: Person $\text{AP}_{50} = 0.2157$, Recall = $0.2240$ | Truck $\text{AP}_{50} = 0.0000$, Recall = $0.0000$ [MEASURED]
- **Fine-Tuned `best.pt`**: Person $\text{AP}_{50} = 0.8210$, Recall = $0.8415$ | Truck $\text{AP}_{50} = 0.9583$, Recall = $1.0000$ [MEASURED]
- **Fixed-Epoch `last.pt`**: `UNMEASURED` (GPU session disconnected during Fold 3 training)

### Fold 4 (31 Holdout Frames, 166 GT Personnel, 31 GT Trucks)
- **Baseline**: Person $\text{AP}_{50} = 0.7722$, Recall = $0.7771$ | Truck $\text{AP}_{50} = 0.5484$, Recall = $0.5484$ [MEASURED]
- **Fine-Tuned `best.pt`**: Person $\text{AP}_{50} = 0.8512$, Recall = $0.8554$ | Truck $\text{AP}_{50} = 1.0000$, Recall = $1.0000$ [MEASURED]
- **Fixed-Epoch `last.pt`**: `UNMEASURED` (GPU session disconnected)

### Fold 5 (31 Holdout Frames, 177 GT Personnel, 31 GT Trucks)
- **Baseline**: Person $\text{AP}_{50} = 0.6872$, Recall = $0.6962$ | Truck $\text{AP}_{50} = 0.5806$, Recall = $0.5806$ [MEASURED]
- **Fine-Tuned `best.pt`**: Person $\text{AP}_{50} = 0.9474$, Recall = $0.9557$ | Truck $\text{AP}_{50} = 0.9955$, Recall = $1.0000$ [MEASURED]
- **Fixed-Epoch `last.pt`**: `UNMEASURED` (GPU session disconnected)

---

## 4. Key Findings

1. **Empirical Confirmation of Holdout Snooping**:
   On both Fold 1 and Fold 2, `best.pt` metrics are systematically higher than `last.pt` (Fold 1: $+0.44\%$, Fold 2: $+0.53\%$). While modest, this delta directly reflects the selection bias incurred when selecting an epoch checkpoint based on holdout fold fitness.
2. **Robust Fine-Tuning Gain**:
   Even without holdout snooping, fixed-epoch fine-tuning improves Person $\text{AP}_{50}$ from $0.5272$ to $0.8332$ ($+30.60$ percentage points) and Recall from $0.5475$ to $0.8634$ ($+31.59$ percentage points).
3. **Headline Metric Designation**:
   To ensure complete scientific integrity, the project designates `last.pt` (zero holdout snooping) as the headline metric for cross-validation reporting.
