"""Content hashes shared by the spine gate and the steps it registers.

A non-code implementer (a question battery, a prompt) is versioned by the hash
of its files; the gate compares the registry's pinned hash with this one, and
model outputs carry it in their basis.
"""
import hashlib
import json
from pathlib import Path


def content_hash(root: Path, paths: list) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.encode() + b"\0" + (root / p).read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()


def json_hash(obj, n: int = 12) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:n]


def text_hash(text: str, n: int = 20) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:n]
