"""
Nebius Token Factory client (OpenAI-compatible) — used ONLY in pre-compute
(teacher labeling / embeddings). Never imported by the offline ranking step.
"""

from __future__ import annotations
import os
from pathlib import Path

BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/")
TEACHER_MODEL = os.environ.get("NEBIUS_TEACHER_MODEL", "Qwen/Qwen3-235B-A22B-Instruct-2507")
EMBED_MODEL = os.environ.get("NEBIUS_EMBED_MODEL", "Qwen/Qwen3-Embedding-8B")


def _find_key() -> str | None:
    if os.environ.get("NEBIUS_API_KEY"):
        return os.environ["NEBIUS_API_KEY"]
    for p in (Path(__file__).resolve().parent.parent / ".env", Path.cwd() / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("NEBIUS_API_KEY") and "=" in line:
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def client():
    from openai import OpenAI
    key = _find_key()
    if not key:
        raise RuntimeError("NEBIUS_API_KEY not found (set env var or .env at repo root)")
    return OpenAI(base_url=BASE_URL, api_key=key)
