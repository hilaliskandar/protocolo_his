from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .models import AplicacaoMunicipal, VersaoDocumento


CAMPOS_MANIFESTO = (
    "aplicacao_id",
    "municipio",
    "documento_id",
    "documento",
    "versao",
    "nome_original",
    "tipo_mime",
    "tamanho_bytes",
    "sha256",
    "situacao_ingestao",
    "duplicado_de_id",
    "origem_recebimento",
    "caminho_arquivo",
    "criado_em",
)


def montar_registros_manifesto(aplicacao: AplicacaoMunicipal) -> list[dict[str, Any]]:
    versoes = VersaoDocumento.objects.filter(documento__aplicacao=aplicacao).select_related(
        "documento",
        "documento__aplicacao__municipio",
        "duplicado_de",
    )
    registros: list[dict[str, Any]] = []
    for versao in versoes.order_by("documento_id", "versao"):
        registros.append(
            {
                "aplicacao_id": aplicacao.pk,
                "municipio": str(aplicacao.municipio),
                "documento_id": versao.documento_id,
                "documento": str(versao.documento),
                "versao": versao.versao,
                "nome_original": versao.nome_original,
                "tipo_mime": versao.mime_type,
                "tamanho_bytes": versao.tamanho_bytes,
                "sha256": versao.sha256,
                "situacao_ingestao": versao.situacao_ingestao,
                "duplicado_de_id": versao.duplicado_de_id,
                "origem_recebimento": versao.origem_recebimento,
                "caminho_arquivo": versao.arquivo.name,
                "criado_em": versao.criado_em.isoformat(),
            }
        )
    return registros


def gerar_manifesto_json(aplicacao: AplicacaoMunicipal, caminho_saida: Path) -> Path:
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    conteudo = {
        "aplicacao": {
            "id": aplicacao.pk,
            "titulo": aplicacao.titulo,
            "municipio": str(aplicacao.municipio),
        },
        "arquivos": montar_registros_manifesto(aplicacao),
    }
    caminho_saida.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return caminho_saida


def gerar_manifesto_csv(aplicacao: AplicacaoMunicipal, caminho_saida: Path) -> Path:
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    with caminho_saida.open("w", encoding="utf-8-sig", newline="") as arquivo_saida:
        escritor = csv.DictWriter(arquivo_saida, fieldnames=CAMPOS_MANIFESTO)
        escritor.writeheader()
        escritor.writerows(montar_registros_manifesto(aplicacao))
    return caminho_saida
