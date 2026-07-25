from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import tiktoken


def sha256_file(path: Path) -> str:
    """Calcula o SHA-256 sem carregar o arquivo inteiro em memória."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def choose_encoding(model: str | None, encoding_name: str | None) -> tuple[Any, str]:
    """Selecion