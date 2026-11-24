"""Train a SegFormer (timm MixTransformer) building-footprint segmenter.

Produces a checkpoint loadable by backend/app/models/segformer_building.py
(smp.Unet + mit encoder, state_dict saved).

Prereqs: local 512x512 tiled imagery + matching masks. Tiles must ALREADY be
geographically split (area A=train, B=val, C=test) — see docs/MODEL_TRAINING.md.
Class ids: 0 = background, 1 = building.
"""
import argparse
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
import segmentation_models_pytorch as smp


class TiledDataset(Dataset):
    def __init__(self, root: Path, split: str):
        self.imgs = sorted((root / split / "images").glob("*.tif"))
        self.masks = sorted((root / split / "masks").glob("*.tif"))
        assert len(self.imgs) == len(self.masks) > 0, f"{split}: empty or mismatched"

    def __len__(self):
        return len(self.imgs)

    def __getitem__(self, i):
        import rasterio as rio

        with rio.open(self.imgs[i]) as src:
            img = src.read()[:3].astype(np.float32) / 255.0
        with rio.open(self.masks[i]) as src:
            m = (src.read(1) != 0).astype(np.int64)
        return torch.from_numpy(img), torch.from_numpy(m)


def compute_metrics(model, loader, device, num_classes=2):
    """Mean IoU + pixel accuracy on a loader."""
    model.eval()
    ious, accs = [], []
    with torch.inference_mode():
        for img, m in loader:
            img, m = img.to(device), m.to(device)
            logits = model(img)
            pred = logits.argmax(dim=1)
            for c in range(num_classes):
                inter = ((pred == c) & (m == c)).sum().float()
                union = ((pred == c) | (m == c)).sum().float()
                ious.append((inter / union).item() if union > 0 else 1.0)
            accs.append((pred == m).float().mean().item())
    return {"mIoU": float(np.mean(ious)), "acc": float(np.mean(accs))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="root with train/val/test dirs")
    ap.add_argument("--out", default="models/checkpoints/building/model.pth")
    ap.add_argument("--encoder", default="mit_b2")  # must match the app's encoder_name
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    train_dl = DataLoader(TiledDataset(args.data, "train"), batch_size=args.batch, shuffle=True, num_workers=2)
    valid_dl = DataLoader(TiledDataset(args.data, "val"), batch_size=args.batch, num_workers=2)

    # Same construction as SegFormerBuilding._build_model (smp preferred backend).
    model = smp.Unet(
        encoder_name=args.encoder,
        encoder_weights="imagenet",   # None for fine-tuning from your own checkpoint
        in_channels=3,
        classes=2,
        activation=None,
    ).to(args.device)

    class_weights = torch.tensor([1.0, 3.0], device=args.device)  # buildings are rare
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optim = torch.optim.AdamW(model.parameters(), lr=args.lr)

    best = 0.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for img, m in train_dl:
            img, m = img.to(args.device), m.to(args.device)
            optim.zero_grad()
            loss = criterion(model(img), m)
            loss.backward()
            optim.step()
            running += loss.item()
        metrics = compute_metrics(model, valid_dl, args.device)
        print(f"epoch {epoch}/{args.epochs}  loss {running/len(train_dl):.4f}  val {metrics}")
        if metrics["mIoU"] > best:
            best = metrics["mIoU"]
            args.out = Path(args.out)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), args.out)
            print(f"  saved {args.out} (mIoU {best:.4f})")

    print(f"done. best val mIoU {best:.4f} -> {args.out}")


if __name__ == "__main__":
    main()