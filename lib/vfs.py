from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_EXCLUDES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
}

KEY_FILE_HINTS = (
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "environment.yml",
    "dockerfile",
    "containerfile",
)


def _is_binary(raw: bytes) -> bool:
    if not raw:
        return False
    if b"\x00" in raw:
        return True
    sample = raw[:1024]
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return ""


@dataclass
class VirtualFileSystem:
    root_url: str
    branch: str
    files: dict[str, str] = field(default_factory=dict)
    tree: list[str] = field(default_factory=list)
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    binary_files: list[str] = field(default_factory=list)

    @classmethod
    def from_directory(
        cls,
        root_url: str,
        branch: str,
        dir_path: str | Path,
        max_file_kb: int = 256,
        max_total_kb: int = 10240,
    ) -> "VirtualFileSystem":
        root = Path(dir_path).resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"directory does not exist: {root}")

        vfs = cls(root_url=root_url, branch=branch)
        max_file_bytes = max_file_kb * 1024
        max_total_bytes = max_total_kb * 1024
        total_text_bytes = 0

        for path in sorted(root.rglob("*")):
            rel_path = path.relative_to(root).as_posix()
            parts = set(path.parts)
            if parts.intersection(DEFAULT_EXCLUDES):
                continue
            if path.is_dir():
                continue
            if path.suffix.lower() in {".pyc", ".pyo", ".so", ".dylib"}:
                continue

            vfs.tree.append(rel_path)
            size = path.stat().st_size
            vfs.metadata[rel_path] = {
                "size_bytes": size,
                "extension": path.suffix.lower(),
            }

            if size > max_file_bytes:
                continue

            raw = path.read_bytes()
            if _is_binary(raw):
                vfs.binary_files.append(rel_path)
                continue

            if total_text_bytes + len(raw) > max_total_bytes:
                continue

            text = _decode_text(raw)
            if not text:
                continue

            vfs.files[rel_path] = text
            total_text_bytes += len(raw)

        return vfs

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_url": self.root_url,
            "branch": self.branch,
            "files": self.files,
            "tree": self.tree,
            "metadata": self.metadata,
            "binary_files": self.binary_files,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VirtualFileSystem":
        return cls(
            root_url=str(data.get("root_url") or ""),
            branch=str(data.get("branch") or "main"),
            files=dict(data.get("files") or {}),
            tree=list(data.get("tree") or []),
            metadata=dict(data.get("metadata") or {}),
            binary_files=list(data.get("binary_files") or []),
        )

    def to_redis(self, redis_client: Any, key: str, ttl_s: int = 3600) -> None:
        redis_client.setex(key, ttl_s, json.dumps(self.to_dict()))

    @classmethod
    def from_redis(cls, redis_client: Any, key: str) -> "VirtualFileSystem":
        raw = redis_client.get(key)
        if raw is None:
            raise KeyError(f"vfs key not found: {key}")
        if isinstance(raw, bytes):
            payload = raw.decode("utf-8")
        else:
            payload = str(raw)
        return cls.from_dict(json.loads(payload))

    def materialize(self, target_dir: str | Path) -> Path:
        root = Path(target_dir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        for rel_path, text in self.files.items():
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def tree_summary(self, max_entries: int = 120) -> str:
        lines = []
        for rel_path in self.tree[:max_entries]:
            size = self.metadata.get(rel_path, {}).get("size_bytes", 0)
            lines.append(f"- {rel_path} ({size} bytes)")
        omitted = max(0, len(self.tree) - max_entries)
        if omitted:
            lines.append(f"- ... {omitted} more files")
        return "\n".join(lines)

    def relevant_files(self, max_items: int = 40) -> dict[str, str]:
        selected: dict[str, str] = {}
        for rel_path in self.tree:
            lower = rel_path.lower()
            base = os.path.basename(lower)
            if any(base == hint for hint in KEY_FILE_HINTS):
                if rel_path in self.files:
                    selected[rel_path] = self.files[rel_path]
                continue

            if lower.endswith(".py") and (
                "train" in base
                or base == "main.py"
                or "finetune" in base
                or "trainer" in base
            ):
                if rel_path in self.files:
                    selected[rel_path] = self.files[rel_path]

            if len(selected) >= max_items:
                break
        return selected
