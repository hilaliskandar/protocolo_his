from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from hashlib import sha256
from importlib import metadata
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import (
    ArtefatoProcessado,
    DiagnosticoPagina,
    DocumentoNormativo,
    ProcessamentoDocumento,
    VersaoDocumento,
)

VERSAO_CODIGO_CONVERSOR = "de39b9f1f86bd089dad9fcc5d95663a2b0600710"


class ErroQualificacaoDocumento(RuntimeError):
    """Erro controlado durante a qualificação de uma versão documental."""


def _serializar(valor: Any) -> Any:
    if is_dataclass(valor):
        return _serializar(asdict(valor))
    if isinstance(valor, Path):
        return str(valor)
    if isinstance(valor, dict):
        return {str(chave): _serializar(item) for chave, item in valor.items()}
    if isinstance(valor, (list, tuple, set)):
        return [_serializar(item) for item in valor]
    return valor


def _carregar_motor():
    try:
        from conversor_his.diagnostic import diagnose_pdf
    except ImportError as erro:
        raise ErroQualificacaoDocumento(
            "O pacote conversor-his não está instalado. Instale a dependência opcional "
            "de qualificação antes de executar o comando."
        ) from erro
    return diagnose_pdf


def _versao_ferramenta() -> str:
    try:
        return metadata.version("conversor-his")
    except metadata.PackageNotFoundError:
        return "desconhecida"


def _calcular_hash_arquivo(versao: VersaoDocumento) -> tuple[str, int, bytes]:
    resumo = sha256()
    tamanho = 0
    cabecalho = b""
    with versao.arquivo.open("rb") as arquivo:
        while bloco := arquivo.read(1024 * 1024):
            if not cabecalho:
                cabecalho = bloco[:8]
            resumo.update(bloco)
            tamanho += len(bloco)
    return resumo.hexdigest(), tamanho, cabecalho


@contextmanager
def _caminho_local(versao: VersaoDocumento) -> Iterator[Path]:
    try:
        caminho = Path(versao.arquivo.path)
    except (AttributeError, NotImplementedError):
        sufixo = Path(versao.nome_original or versao.arquivo.name).suffix or ".pdf"
        with NamedTemporaryFile(suffix=sufixo, delete=False) as temporario:
            with versao.arquivo.open("rb") as origem:
                while bloco := origem.read(1024 * 1024):
                    temporario.write(bloco)
            caminho = Path(temporario.name)
        try:
            yield caminho
        finally:
            caminho.unlink(missing_ok=True)
        return
    yield caminho


def _classificar_rota(paginas: list[Any]) -> str:
    rotas = [pagina.route for pagina in paginas]
    visuais = sum(rota in {"map", "structured", "hybrid", "manual"} for rota in rotas)
    nativas = rotas.count("native")
    ocr = rotas.count("ocr")

    if visuais:
        return ProcessamentoDocumento.RotaDocumento.VISUAL_COMPLEXO
    if nativas and ocr:
        return ProcessamentoDocumento.RotaDocumento.MISTO
    if ocr:
        return ProcessamentoDocumento.RotaDocumento.OCR
    if nativas:
        return ProcessamentoDocumento.RotaDocumento.TEXTO_NATIVO
    return ProcessamentoDocumento.RotaDocumento.MANUAL


def _metricas_documento(diagnostico: Any) -> dict[str, Any]:
    paginas = list(diagnostico.pages)
    contagem_rotas: dict[str, int] = {}
    contagem_tipos: dict[str, int] = {}
    for pagina in paginas:
        contagem_rotas[pagina.route] = contagem_rotas.get(pagina.route, 0) + 1
        contagem_tipos[pagina.page_type] = contagem_tipos.get(pagina.page_type, 0) + 1

    return {
        "paginas_total": diagnostico.page_count,
        "paginas_diagnosticadas": len(paginas),
        "caracteres_total": sum(pagina.character_count for pagina in paginas),
        "paginas_com_texto_nativo": sum(pagina.has_native_text for pagina in paginas),
        "paginas_com_imagens": sum(pagina.content_image_count > 0 for pagina in paginas),
        "paginas_com_tabela_suspeita": sum(pagina.suspected_table for pagina in paginas),
        "paginas_com_mapa_suspeito": sum(pagina.suspected_map for pagina in paginas),
        "paginas_com_texto_rotacionado": sum(pagina.rotated_text_detected for pagina in paginas),
        "rotas": contagem_rotas,
        "tipos_paginas": contagem_tipos,
    }


def _dados_tecnicos_pagina(pagina: Any) -> dict[str, Any]:
    dados = _serializar(pagina)
    for campo in (
        "page_number",
        "route",
        "page_type",
        "has_native_text",
        "character_count",
        "content_image_count",
        "suspected_table",
        "suspected_map",
        "native_extraction_mode",
        "rotated_text_detected",
        "warnings",
    ):
        dados.pop(campo, None)
    return dados


def _gravar_artefato(processamento: ProcessamentoDocumento, diagnostico: Any) -> None:
    conteudo = json.dumps(
        _serializar(diagnostico),
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    resumo = sha256(conteudo).hexdigest()
    artefato = ArtefatoProcessado(
        processamento=processamento,
        tipo=ArtefatoProcessado.Tipo.DIAGNOSTICO_JSON,
        sha256=resumo,
        tamanho_bytes=len(conteudo),
        mime_type="application/json",
        metadados={"formato": "DocumentDiagnosis", "codificacao": "utf-8"},
    )
    artefato.arquivo.save(
        f"diagnostico-{processamento.pk}.json",
        ContentFile(conteudo),
        save=False,
    )
    artefato.save()


def _validar_diagnostico(diagnostico: Any, hash_esperado: str) -> None:
    paginas = list(diagnostico.pages)
    if diagnostico.sha256 != hash_esperado:
        raise ErroQualificacaoDocumento(
            "O hash calculado pelo motor de diagnóstico não corresponde ao arquivo ingerido."
        )
    if diagnostico.page_count <= 0:
        raise ErroQualificacaoDocumento("O PDF não possui páginas diagnosticáveis.")
    if len(paginas) != diagnostico.page_count:
        raise ErroQualificacaoDocumento(
            "O diagnóstico não abrange todas as páginas do PDF."
        )
    numeros = [pagina.page_number for pagina in paginas]
    if numeros != list(range(1, diagnostico.page_count + 1)):
        raise ErroQualificacaoDocumento("A numeração das páginas diagnosticadas é inconsistente.")


def qualificar_versao(
    versao: VersaoDocumento,
    *,
    forcar: bool = False,
    parametros: dict[str, Any] | None = None,
) -> ProcessamentoDocumento:
    parametros = parametros or {"min_native_chars": 40}
    concluido = versao.processamentos.filter(
        etapa=ProcessamentoDocumento.Etapa.QUALIFICACAO,
        status=ProcessamentoDocumento.Status.CONCLUIDO,
        versao_codigo=VERSAO_CODIGO_CONVERSOR,
        parametros=parametros,
    ).first()
    if concluido and not forcar:
        return concluido

    processamento = ProcessamentoDocumento.objects.create(
        versao_documento=versao,
        etapa=ProcessamentoDocumento.Etapa.QUALIFICACAO,
        status=ProcessamentoDocumento.Status.EM_EXECUCAO,
        ferramenta="conversor-his",
        versao_ferramenta=_versao_ferramenta(),
        versao_codigo=VERSAO_CODIGO_CONVERSOR,
        parametros=parametros,
        iniciado_em=timezone.now(),
    )
    inicio = monotonic()

    try:
        hash_atual, tamanho_atual, cabecalho = _calcular_hash_arquivo(versao)
        if hash_atual != versao.sha256:
            raise ErroQualificacaoDocumento(
                "O hash atual do arquivo não corresponde ao hash registrado na ingestão."
            )
        if tamanho_atual != versao.tamanho_bytes:
            raise ErroQualificacaoDocumento(
                "O tamanho atual do arquivo não corresponde ao tamanho registrado na ingestão."
            )
        if not cabecalho.startswith(b"%PDF-"):
            raise ErroQualificacaoDocumento("O arquivo não possui assinatura PDF válida.")

        motor = _carregar_motor()
        with _caminho_local(versao) as caminho:
            diagnostico = motor(
                caminho,
                min_native_chars=int(parametros["min_native_chars"]),
            )
        _validar_diagnostico(diagnostico, versao.sha256)
        rota = _classificar_rota(list(diagnostico.pages))
        metricas = _metricas_documento(diagnostico)

        with transaction.atomic():
            processamento.rota_documento = rota
            processamento.metricas = metricas
            processamento.avisos = [
                aviso
                for pagina in diagnostico.pages
                for aviso in pagina.warnings
            ]
            processamento.status = ProcessamentoDocumento.Status.CONCLUIDO
            processamento.concluido_em = timezone.now()
            processamento.duracao_segundos = monotonic() - inicio
            processamento.save()

            DiagnosticoPagina.objects.bulk_create(
                [
                    DiagnosticoPagina(
                        processamento=processamento,
                        numero_pagina=pagina.page_number,
                        rota=pagina.route,
                        tipo_pagina=pagina.page_type,
                        possui_texto_nativo=pagina.has_native_text,
                        quantidade_caracteres=pagina.character_count,
                        quantidade_imagens=pagina.content_image_count,
                        tabela_suspeita=pagina.suspected_table,
                        mapa_suspeito=pagina.suspected_map,
                        modo_extracao=pagina.native_extraction_mode,
                        texto_rotacionado=pagina.rotated_text_detected,
                        avisos=pagina.warnings,
                        dados_tecnicos=_dados_tecnicos_pagina(pagina),
                    )
                    for pagina in diagnostico.pages
                ]
            )
            _gravar_artefato(processamento, diagnostico)
            if not versao.mime_type:
                versao.mime_type = "application/pdf"
                versao.save(update_fields=["mime_type"])
            versao.documento.status = DocumentoNormativo.Status.VERIFICADO
            versao.documento.save(update_fields=["status", "atualizado_em"])
        return processamento
    except Exception as erro:
        processamento.status = ProcessamentoDocumento.Status.FALHOU
        processamento.mensagem_erro = str(erro)
        processamento.concluido_em = timezone.now()
        processamento.duracao_segundos = monotonic() - inicio
        processamento.rota_documento = ProcessamentoDocumento.RotaDocumento.MANUAL
        processamento.save()
        versao.documento.status = DocumentoNormativo.Status.QUARENTENA
        versao.documento.save(update_fields=["status", "atualizado_em"])
        if isinstance(erro, ErroQualificacaoDocumento):
            raise
        raise ErroQualificacaoDocumento(str(erro)) from erro
