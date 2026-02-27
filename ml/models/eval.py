"""Evaluation metrics for PyTorch models.

All functions are pure (no side effects) and operate over a DataLoader.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torch.utils.data import DataLoader


def accuracy(model: nn.Module, loader: DataLoader, device: str) -> float:
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for data, target in loader:
            data, target = data.to(device), target.to(device)
            pred = model(data).argmax(dim=1)
            correct += (pred == target).sum().item()
            total += len(target)
    return correct / total if total else 0.0


def avg_loss(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: str,
) -> float:
    model.eval()
    total_loss = 0.0
    n = 0
    with torch.no_grad():
        for data, target in loader:
            data, target = data.to(device), target.to(device)
            total_loss += criterion(model(data), target).item()
            n += 1
    return total_loss / n if n else 0.0
