"""Model artifact registry with versioned directory structure.

Directory layout::

    ml/artifacts/
        {experiment}/
            {version}/          (e.g. v1, v2, or ISO timestamp)
                model.pt        PyTorch state-dict
                meta.json       hyperparams, metrics, commit SHA
            latest -> {version} (symlink updated on each save)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import torch.nn as nn

# Navigate from ml/models/registry.py up to project root (ml/models -> ml -> root)
_DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "artifacts"
_LATEST = "latest"


class ModelRegistry:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or _DEFAULT_ROOT)

    def _version_dir(self, experiment: str, version: str) -> Path:
        return self.root / experiment / version

    def save(
        self,
        model: "nn.Module",
        experiment: str,
        version: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        import torch

        version = version or f"v{int(time.time())}"
        vdir = self._version_dir(experiment, version)
        vdir.mkdir(parents=True, exist_ok=True)

        torch.save(model.state_dict(), vdir / "model.pt")
        (vdir / "meta.json").write_text(
            json.dumps(metadata or {}, indent=2), encoding="utf-8"
        )

        latest = self.root / experiment / _LATEST
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(version)

        return vdir

    def load(
        self,
        model: "nn.Module",
        experiment: str,
        version: str = _LATEST,
        map_location: str | None = None,
    ) -> "nn.Module":
        import torch

        vdir = self.root / experiment / version
        if version == _LATEST and vdir.is_symlink():
            vdir = vdir.resolve()
        state = torch.load(vdir / "model.pt", map_location=map_location)
        model.load_state_dict(state)
        return model

    def list_versions(self, experiment: str) -> list[str]:
        exp_dir = self.root / experiment
        if not exp_dir.exists():
            return []
        return sorted(
            d.name for d in exp_dir.iterdir() if d.is_dir() and d.name != _LATEST
        )

    def metadata(self, experiment: str, version: str = _LATEST) -> dict[str, Any]:
        vdir = self.root / experiment / version
        if version == _LATEST and vdir.is_symlink():
            vdir = vdir.resolve()
        meta_path = vdir / "meta.json"
        if not meta_path.exists():
            return {}
        return json.loads(meta_path.read_text(encoding="utf-8"))
