#!/usr/bin/env python3
"""
Aegis Command - Model Fine-Tuning Pipeline.

Fine-tunes YOLOv8 using transfer learning on the 155-frame verified
human-annotated dataset (1,948 ground truth boxes).

Architecture:
- Base Checkpoint: Pretrained YOLOv8 (yolov8n.pt)
- Backbone Freezing: Freeze layers 0..9 to preserve foundational visual representations
- Tuned Head: 4-class tactical detection head (person, car, truck, bus)
- Hardware Tuning: Configured for Intel CPU & 4GB RAM budget (single worker, batch=4, imgsz=640)
- Deliverable: vision/models/aegis_finetuned/weights/best.pt
"""

import sys
import os
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_YAML = REPO_ROOT / "vision" / "data" / "aegis_data.yaml"
MODELS_DIR = REPO_ROOT / "vision" / "models"


def run_training(
    base_model: str = "yolov8n.pt",
    epochs: int = 3,
    imgsz: int = 640,
    batch: int = 2,
    freeze_layers: int = 10,
    lr0: float = 0.005
):
    if not DATA_YAML.exists():
        print(f"Error: dataset YAML not found at {DATA_YAML}. Run split_dataset.py first.", file=sys.stderr)
        sys.exit(1)

    print("=" * 65)
    print("AEGIS VISION GROUND-TRUTH FINE-TUNING")
    print(f"Base Checkpoint:   {base_model}")
    print(f"Dataset Config:    {DATA_YAML}")
    print(f"Epochs:            {epochs}")
    print(f"Image Size:        {imgsz}x{imgsz}")
    print(f"Batch Size:        {batch}")
    print(f"Frozen Layers:     {freeze_layers} (Backbone frozen)")
    print(f"Learning Rate:     {lr0}")
    print(f"Compute Device:    CPU (Intel Core i3)")
    print("=" * 65)

    import csv
    from ultralytics import YOLO
    import ultralytics.engine.trainer as trainer_module

    # Monkeypatch to avoid polars requirement on legacy CPU architectures
    def safe_read_results_csv(self):
        try:
            if hasattr(self, "csv") and Path(self.csv).exists():
                with open(self.csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    data = {col.strip(): [] for col in (reader.fieldnames or [])}
                    for row in reader:
                        for k, v in row.items():
                            try:
                                val = float(v)
                            except (ValueError, TypeError):
                                val = v
                            data[k.strip()].append(val)
                    return data
        except Exception:
            pass
        return {}

    trainer_module.BaseTrainer.read_results_csv = safe_read_results_csv

    model = YOLO(base_model)

    t_start = time.time()
    results = model.train(
        data=str(DATA_YAML),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device="cpu",
        workers=0,
        freeze=freeze_layers,
        lr0=lr0,
        lrf=0.01,
        warmup_epochs=1,
        patience=5,
        cache=False,
        amp=False,
        project=str(MODELS_DIR),
        name="aegis_finetuned",
        exist_ok=True,
        verbose=True,
        plots=True,
        save=True
    )
    elapsed = time.time() - t_start

    best_weights = MODELS_DIR / "aegis_finetuned" / "weights" / "best.pt"
    print("\n" + "=" * 65)
    print("FINE-TUNING COMPLETED")
    print(f"Total Training Time: {elapsed:.1f}s ({elapsed/60.0:.2f} min)")
    print(f"Best Weights Path:   {best_weights}")
    print("=" * 65)
    return str(best_weights)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fine-tune YOLO model on verified aerial annotations.")
    parser.add_argument("--base", default="yolov8n.pt", help="Pretrained base model weights")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Training image resolution")
    parser.add_argument("--batch", type=int, default=4, help="Batch size")
    parser.add_argument("--freeze", type=int, default=10, help="Number of layers to freeze")
    parser.add_argument("--lr", type=float, default=0.005, help="Initial learning rate")
    args = parser.parse_args()

    run_training(
        base_model=args.base,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        freeze_layers=args.freeze,
        lr0=args.lr
    )
