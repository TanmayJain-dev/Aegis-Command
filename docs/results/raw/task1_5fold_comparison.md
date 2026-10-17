# Aegis Command - Cross-Validation Protocol Comparison Table

## 1. Protocol Overview

This document presents the empirical comparison across three model evaluation protocols on the 155-frame UAV dataset:
1. **Zero-Shot Pre-trained Baseline** (`yolov8m.pt` @ 1280px, evaluated on each holdout fold).
2. **Fine-Tuned `best.pt`** (optimistic baseline: checkpoint selected via validation set fitness snooping on each holdout fold).
3. **Fixed-Epoch `last.pt`** (headline metric: trained for exactly 50 epochs with `val=False`, zero holdout snooping, evaluated on each holdout fold).

---

## 2. Headline Summary Table (Like-for-Like 5-Fold Comparison)

| Metric | Pre-trained Baseline (Mean ± Std) | Fine-Tuned `best.pt` (Optimistic, Validation-Selected) | Fixed-Epoch `last.pt` (Headline, Zero Snooping) | Delta (`last.pt` vs Baseline) | Status |
|:---|:---:|:---:|:---:|:---:|:---|
| **Person $\text{AP}_{50}$** | $0.5272 \pm 0.2321$ | $0.8591 \pm 0.0612$ | $0.8275 \pm 0.0524$ | $+0.3004$ (+30.04 pp) | [MEASURED] |
| **Person Recall@0.25** | $0.5475 \pm 0.2248$ | $0.8788 \pm 0.0514$ | $0.8458 \pm 0.0439$ | $+0.2983$ (+29.83 pp) | [MEASURED] |
| **Vehicle (Truck) $\text{AP}_{50}$** | $0.5868 \pm 0.3699$ | $0.8042 \pm 0.2572$ | $0.7720 \pm 0.3615$ | $+0.1852$ (+18.52 pp) | [MEASURED] |
| **Vehicle (Truck) Recall@0.25** | $0.5870 \pm 0.3701$ | $0.8318 \pm 0.2405$ | $0.7806 \pm 0.3503$ | $+0.1937$ (+19.37 pp) | [MEASURED] |

> **Statistical note**: Sample standard deviation calculated with Bessel's correction ($ddof=1$, $s = \sqrt{\frac{1}{N-1}\sum (x_i - \bar{x})^2}$).

---

## 3. Per-Fold Breakdown (Direct from Raw `eval_results.json`)

### Fold 1 (31 Holdout Frames)
- **Baseline**: Person $\text{AP}_{50} = 0.5998$, Recall = $0.6229$ | Truck $\text{AP}_{50} = 0.8696$, Recall = $0.8704$ [MEASURED]
- **Fine-Tuned `best.pt`**: Person $\text{AP}_{50} = 0.8870$, Recall = $0.9068$ | Truck $\text{AP}_{50} = 0.4346$, Recall = $0.4815$ [MEASURED]
- **Fixed-Epoch `last.pt`**: Person $\text{AP}_{50} = 0.8511$, Recall = $0.8708$ | Truck $\text{AP}_{50} = 0.1383$, Recall = $0.1667$ [MEASURED]
- *Holdout Snooping Bias*: `best.pt` inflated Person $\text{AP}_{50}$ by $+0.0359$ (+3.59 pp) and Person Recall by $+0.0360$ (+3.60 pp).

### Fold 2 (31 Holdout Frames)
- **Baseline**: Person $\text{AP}_{50} = 0.3610$, Recall = $0.4174$ | Truck $\text{AP}_{50} = 0.9355$, Recall = $0.9355$ [MEASURED]
- **Fine-Tuned `best.pt`**: Person $\text{AP}_{50} = 0.7891$, Recall = $0.8348$ | Truck $\text{AP}_{50} = 0.6327$, Recall = $0.6774$ [MEASURED]
- **Fixed-Epoch `last.pt`**: Person $\text{AP}_{50} = 0.7995$, Recall = $0.8348$ | Truck $\text{AP}_{50} = 0.8883$, Recall = $0.9032$ [MEASURED]
- *Holdout Snooping Bias*: `best.pt` inflated Person $\text{AP}_{50}$ by $-0.0104$ (-1.04 pp) and Person Recall by $+0.0000$ (+0.00 pp).

### Fold 3 (31 Holdout Frames)
- **Baseline**: Person $\text{AP}_{50} = 0.2157$, Recall = $0.2240$ | Truck $\text{AP}_{50} = 0.0000$, Recall = $0.0000$ [MEASURED]
- **Fine-Tuned `best.pt`**: Person $\text{AP}_{50} = 0.8210$, Recall = $0.8415$ | Truck $\text{AP}_{50} = 0.9583$, Recall = $1.0000$ [MEASURED]
- **Fixed-Epoch `last.pt`**: Person $\text{AP}_{50} = 0.7541$, Recall = $0.7814$ | Truck $\text{AP}_{50} = 0.8333$, Recall = $0.8333$ [MEASURED]
- *Holdout Snooping Bias*: `best.pt` inflated Person $\text{AP}_{50}$ by $+0.0669$ (+6.69 pp) and Person Recall by $+0.0601$ (+6.01 pp).

### Fold 4 (31 Holdout Frames)
- **Baseline**: Person $\text{AP}_{50} = 0.7722$, Recall = $0.7771$ | Truck $\text{AP}_{50} = 0.5484$, Recall = $0.5484$ [MEASURED]
- **Fine-Tuned `best.pt`**: Person $\text{AP}_{50} = 0.8512$, Recall = $0.8554$ | Truck $\text{AP}_{50} = 1.0000$, Recall = $1.0000$ [MEASURED]
- **Fixed-Epoch `last.pt`**: Person $\text{AP}_{50} = 0.8417$, Recall = $0.8434$ | Truck $\text{AP}_{50} = 1.0000$, Recall = $1.0000$ [MEASURED]
- *Holdout Snooping Bias*: `best.pt` inflated Person $\text{AP}_{50}$ by $+0.0095$ (+0.95 pp) and Person Recall by $+0.0120$ (+1.20 pp).

### Fold 5 (31 Holdout Frames)
- **Baseline**: Person $\text{AP}_{50} = 0.6872$, Recall = $0.6962$ | Truck $\text{AP}_{50} = 0.5806$, Recall = $0.5806$ [MEASURED]
- **Fine-Tuned `best.pt`**: Person $\text{AP}_{50} = 0.9474$, Recall = $0.9557$ | Truck $\text{AP}_{50} = 0.9955$, Recall = $1.0000$ [MEASURED]
- **Fixed-Epoch `last.pt`**: Person $\text{AP}_{50} = 0.8913$, Recall = $0.8987$ | Truck $\text{AP}_{50} = 1.0000$, Recall = $1.0000$ [MEASURED]
- *Holdout Snooping Bias*: `best.pt` inflated Person $\text{AP}_{50}$ by $+0.0561$ (+5.61 pp) and Person Recall by $+0.0570$ (+5.70 pp).
