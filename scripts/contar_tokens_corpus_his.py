from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
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
    """Seleciona o encoding e registra a origem da decisão."""
    if encoding_name:
        return tiktoken.get_encoding(encoding_name), "explicit_encoding"
    if model:
        try:
            return tiktoken.encoding_for_model(model), "model_mapping"
        except KeyError:
            return tiktoken.get_encoding("o200k_base"), "fallback_o200k_base"
    return tiktoken.get_encoding("o200k_base"), "default_o200k_base"


def count_markdown_files(root: Path, encoding: Any) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        token_count = len(encoding.encode_ordinary(text))
        records.append(
            {
                "caminho_relativo": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "caracteres": len(text),
                "tokens": token_count,
                "tokens_por_1000_caracteres": (
                    round(1000 * token_count / len(text), 3) if text else 0
                ),
                "sha256": sha256_file(path),
            }
        )
    return records


def write_csv(path: Path, records: list[dict[str, object]]) -> None:
    fields = [
        "caminho_relativo",
        "bytes",
        "caracteres",
        "tokens",
        "tokens_por_1000_caracteres",
        "sha256",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def build_summary(
    *,
    root: Path,
    model: str | None,
    encoding: Any,
    encoding_source: str,
    records: list[dict[str, object]],
    csv_path: Path,
) -> dict[str, object]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "model_requested": model,
        "encoding": encoding.name,
        "encoding_source": encoding_source,
        "tiktoken_version": importlib.metadata.version("tiktoken"),
        "file_count": len(records),
        "total_bytes": sum(int(record["bytes"]) for record in records),
        "total_characters": sum(int(record["caracteres"]) for record in records),
        "total_tokens": sum(int(record["tokens"]) for record in records),
        "csv_output": str(csv_path.resolve()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Conta tokens dos Markdown produzidos pelo pipeline do Protocolo HIS."
    )
    parser.add_argument("--raiz", type=Path, required=True)
    parser.add_argument("--modelo")
    parser.add_argument("--encoding")
    parser.add_argument("--csv", type=Path, default=Path("tokens_por_arquivo.csv"))
    parser.add_argument("--json", type=Path, default=Path("resumo_tokens.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.raiz.resolve()
    if not root.is_dir():
        raise SystemExit(f"Diretório não encontrado: {root}")

    encoding, encoding_source = choose_encoding(args.modelo, args.encoding)
    records = count_markdown_files(root, encoding)
    write_csv(args.csv, records)

    summary = build_summary(
        root=root,
        model=args.modelo,
        encoding=encoding,
        encoding_source=encoding_source,
        records=records,
        csv_path=args.csv,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
