from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import torch
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter

from lib import get_logger

logger = get_logger("ml-trainloop")


@runtime_checkable
class TrainerCallback(Protocol):
    """Minimal interface for training hooks (MLFlow, WANDB, custom)."""

    def on_epoch_end(self, epoch: int, avg_loss: float, trainer: "Trainer") -> None:
        ...


class Trainer:
    def __init__(
        self,
        model: nn.Module,
        train_loader,
        log_dir: str = "../tensorboard",
        device: str | None = None,
        artifact_dir: str | Path | None = None,
        callbacks: list[TrainerCallback] | None = None,
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)
        self.train_loader = train_loader
        self.optimizer = torch.optim.Adam(model.parameters())
        self.criterion = nn.CrossEntropyLoss()
        self.writer = SummaryWriter(log_dir)
        self.artifact_dir = Path(artifact_dir) if artifact_dir else None
        self.callbacks: list[TrainerCallback] = callbacks or []
        self.step = 0
        logger.info("training initialized device=%s", self.device)

    def train_epoch(self) -> float:
        self.model.train()
        total_loss = 0.0
        batch_count = 0
        for batch_idx, (data, target) in enumerate(self.train_loader):
            data, target = data.to(self.device), target.to(self.device)
            self.optimizer.zero_grad()
            loss = self.criterion(self.model(data), target)
            loss.backward()
            self.optimizer.step()
            total_loss += float(loss.item())
            batch_count += 1
            if batch_idx % 100 == 0:
                self.writer.add_scalar("Loss/Train", loss.item(), self.step)
                self.step += 1
        return total_loss / batch_count if batch_count else 0.0

    def save_checkpoint(self, name: str = "checkpoint.pt") -> Path:
        if self.artifact_dir is None:
            raise RuntimeError("artifact_dir not configured on Trainer")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifact_dir / name
        torch.save(self.model.state_dict(), path)
        return path

    def train(self, epochs: int) -> None:
        for epoch in range(epochs):
            loss = self.train_epoch()
            logger.info("epoch=%d avg_loss=%.6f", epoch + 1, loss)
            for cb in self.callbacks:
                cb.on_epoch_end(epoch + 1, loss, self)
        self.writer.close()
