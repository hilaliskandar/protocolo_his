from __future__ import annotations

import json
import zipfile
from hashlib import sha256
from importlib import metadata
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import ArtefatoProcessado, DocumentoNormativo, ProcessamentoDocumento, VersaoDocumento
from .qualificacao import VERSAO_CODIGO_CONVERSOR, _caminho_local


class ErroConversaoDocumento(RuntimeError):
    """Erro controlado durante a conversão de uma versão documental."""

    def __init__(
        self,
        mensagem: str,
        *,
        categoria: str = "tecnico",
        codigo: str = "conversao_falhou",
        acao: str = "Revise o arquivo e tente novamente.",
        detalhes: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(mensagem)
        self.categoria = categoria
        self.codigo = codigo
        self.acao = acao
        self.detalhes = detalhes or {}

    def para_registro(self) -> dict[str, Any]:
        return {
            "categoria": self.categoria,
            "codigo": self.codigo,
            "mensagem": str(self),
            "acao": self.acao,
            "detalhes": self.detalhes,
        }


def _versao_ferramenta() -> str:
    try:
        return metadata.version("conversor-his")
    except metadata.PackageNotFoundError:
        return "desconhecida"


def _carregar_motor():
    try:
        from conversor_his.converter import convert_pdf
    except ImportError as erro:
        raise ErroConversaoDocumento(
            "O pacote conversor-his não está instalado. Instale a dependência opcional "
            "de qualificação e conversão antes de executar o comando."
        ) from erro
    return convert_pdf


def _hash_bytes(conteudo: bytes) -> str:
    return sha256(conteudo).hexdigest()


def _gravar_artefato(
    processamento: ProcessamentoDocumento,
    *,
    tipo: str,
    nome: str,
    conteudo: bytes,
    mime_type: str,
    metadados: dict[str, Any] | None = None,
) -> ArtefatoProcessado:
    artefato = ArtefatoProcessado(
        processamento=processamento,
        tipo=tipo,
        sha256=_hash_bytes(conteudo),
        tamanho_bytes=len(conteudo),
        mime_type=mime_type,
        metadados=metadados or {},
    )
    artefato.arquivo.save(nome, ContentFile(conteudo), save=False)
    artefato.save()
    return artefato


def _criar_pacote(saida: Path) -> bytes:
    destino = saida / "pacote-conversao.zip"
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as pacote:
        for caminho in sorted(saida.rglob("*")):
            if not caminho.is_file() or caminho == destino:
                continue
            pacote.write(caminho, caminho.relative_to(saida).as_posix())
    return destino.read_bytes()


def _carregar_manifesto(markdown_path: Path) -> tuple[Path, dict[str, Any]]:
    candidatos = [
        markdown_path.with_suffix(".manifest.json"),
        markdown_path.parent / f"{markdown_path.stem}.manifest.json",
        markdown_path.parent.parent / f"{markdown_path.stem}.manifest.json",
    ]
    for candidato in candidatos:
        if candidato.exists():
            return candidato, json.loads(candidato.read_text(encoding="utf-8"))
    raise ErroConversaoDocumento("O conversor não produziu o manifesto esperado.")


def _metricas_manifesto(manifesto: dict[str, Any]) -> dict[str, Any]:
    campos_listas = (
        "used_ocr_pages",
        "map_pages",
        "map_candidate_pages",
        "map_cover_pages",
        "table_pages",
        "table_candidate_pages",
        "raster_table_pages",
        "diagram_pages",
        "coordinate_register_pages",
        "ocr_review_image_pages",
        "review_pages",
        "decorative_pages",
        "rotated_text_pages",
    )
    metricas: dict[str, Any] = {
        "paginas_total": manifesto.get("page_count", 0),
        "markdown_tamanho_bytes": manifesto.get("markdown_size_bytes", 0),
        "tempo_conversor_segundos": manifesto.get("processing_seconds"),
    }
    for campo in campos_listas:
        valores = manifesto.get(campo, []) or []
        metricas[f"total_{campo}"] = len(valores)
        metricas[campo] = valores
    metricas["total_ativos"] = len(manifesto.get("asset_paths", []) or [])
    return metricas


def _validar_arquivo_fonte(versao: VersaoDocumento) -> None:
    resumo = sha256()
    tamanho = 0
    assinatura = b""
    with versao.arquivo.open("rb") as arquivo:
        while bloco := arquivo.read(1024 * 1024):
            if not assinatura:
                assinatura = bloco[:8]
            resumo.update(bloco)
            tamanho += len(bloco)
    if resumo.hexdigest() != versao.sha256:
        raise ErroConversaoDocumento(
            "O hash atual do arquivo não corresponde ao hash registrado na ingestão.",
            categoria="governanca",
            codigo="arquivo_hash_divergente",
            acao="Interrompa a conversão e reingira a versão original para restaurar a integridade.",
        )
    if tamanho != versao.tamanho_bytes:
        raise ErroConversaoDocumento(
            "O tamanho atual do arquivo não corresponde ao tamanho registrado na ingestão.",
            categoria="governanca",
            codigo="arquivo_tamanho_divergente",
            acao="Reingira a versão para alinhar os metadados de tamanho antes de converter.",
        )
    if tamanho <= 0:
        raise ErroConversaoDocumento(
            "O arquivo está vazio e não pode ser convertido.",
            categoria="conteudo",
            codigo="arquivo_vazio",
            acao="Substitua o documento por um PDF não vazio.",
        )
    if not assinatura.startswith(b"%PDF-"):
        raise ErroConversaoDocumento(
            "O arquivo não possui assinatura PDF válida.",
            categoria="conteudo",
            codigo="assinatura_pdf_invalida",
            acao="Substitua por um PDF válido antes de converter.",
        )


def converter_versao(
    versao: VersaoDocumento,
    *,
    forcar: bool = False,
    parametros: dict[str, Any] | None = None,
) -> ProcessamentoDocumento:
    parametros = parametros or {"dpi": 300}
    concluido = versao.processamentos.filter(
        etapa=ProcessamentoDocumento.Etapa.CONVERSAO,
        status=ProcessamentoDocumento.Status.CONCLUIDO,
        versao_codigo=VERSAO_CODIGO_CONVERSOR,
        parametros=parametros,
    ).first()
    if concluido and not forcar:
        return concluido

    qualificacao = versao.processamentos.filter(
        etapa=ProcessamentoDocumento.Etapa.QUALIFICACAO,
        status=ProcessamentoDocumento.Status.CONCLUIDO,
    ).first()
    if not qualificacao:
        raise ErroConversaoDocumento(
            "A versão precisa de uma qualificação concluída antes da conversão."
        )

    processamento = ProcessamentoDocumento.objects.create(
        versao_documento=versao,
        etapa=ProcessamentoDocumento.Etapa.CONVERSAO,
        status=ProcessamentoDocumento.Status.EM_EXECUCAO,
        rota_documento=qualificacao.rota_documento,
        ferramenta="conversor-his",
        versao_ferramenta=_versao_ferramenta(),
        versao_codigo=VERSAO_CODIGO_CONVERSOR,
        parametros=parametros,
        iniciado_em=timezone.now(),
    )
    inicio = monotonic()

    try:
        _validar_arquivo_fonte(versao)
        motor = _carregar_motor()
        with TemporaryDirectory(prefix="protocolo-his-conversao-") as temporario:
            saida = Path(temporario) / "saida"
            saida.mkdir(parents=True)
            with _caminho_local(versao) as caminho:
                markdown_path = Path(
                    motor(
                        caminho,
                        saida,
                        dpi=int(parametros["dpi"]),
                        source_reference=versao.arquivo.name,
                    )
                )
            if not markdown_path.exists():
                raise ErroConversaoDocumento("O conversor não produziu o Markdown esperado.")

            markdown = markdown_path.read_bytes()
            manifesto_path, manifesto = _carregar_manifesto(markdown_path)
            if manifesto.get("source_sha256") != versao.sha256:
                raise ErroConversaoDocumento(
                    "O hash do arquivo-fonte no manifesto não corresponde à versão ingerida.",
                    categoria="governanca",
                    codigo="manifesto_hash_fonte_divergente",
                    acao="Reexecute a conversão e valide a cadeia de custódia da entrada.",
                )
            if manifesto.get("markdown_sha256") != _hash_bytes(markdown):
                raise ErroConversaoDocumento(
                    "O hash do Markdown no manifesto não corresponde ao artefato produzido.",
                    categoria="tecnico",
                    codigo="manifesto_hash_markdown_divergente",
                    acao="Reexecute a conversão para regenerar os artefatos de saída.",
                )
            pacote = _criar_pacote(saida)
            metricas = _metricas_manifesto(manifesto)

            with transaction.atomic():
                _gravar_artefato(
                    processamento,
                    tipo=ArtefatoProcessado.Tipo.MARKDOWN,
                    nome=f"{markdown_path.stem}.md",
                    conteudo=markdown,
                    mime_type="text/markdown",
                    metadados={
                        "manifesto": manifesto_path.name,
                        "paginas": manifesto.get("page_count"),
                        "sha256_fonte": manifesto.get("source_sha256"),
                    },
                )
                _gravar_artefato(
                    processamento,
                    tipo=ArtefatoProcessado.Tipo.OUTRO,
                    nome=f"{markdown_path.stem}.conversao.zip",
                    conteudo=pacote,
                    mime_type="application/zip",
                    metadados={
                        "conteudo": [
                            "manifesto",
                            "tokens OCR",
                            "estrutura OCR",
                            "ativos visuais",
                            "Markdown",
                        ],
                        "manifesto": manifesto,
                    },
                )
                processamento.metricas = metricas
                processamento.avisos = [
                    f"{len(manifesto.get('review_pages', []) or [])} página(s) requerem revisão."
                ] if manifesto.get("review_pages") else []
                processamento.status = ProcessamentoDocumento.Status.CONCLUIDO
                processamento.concluido_em = timezone.now()
                processamento.duracao_segundos = monotonic() - inicio
                processamento.save()
                if versao.documento.status == DocumentoNormativo.Status.RECEBIDO:
                    versao.documento.status = DocumentoNormativo.Status.VERIFICADO
                    versao.documento.save(update_fields=["status", "atualizado_em"])
        return processamento
    except Exception as erro:
        falha = erro
        if not isinstance(falha, ErroConversaoDocumento):
            if isinstance(erro, ValueError):
                falha = ErroConversaoDocumento(
                    "O PDF aparenta estar malformado para conversão automatizada.",
                    categoria="conteudo",
                    codigo="pdf_malformado",
                    acao="Substitua o arquivo por um PDF íntegro ou encaminhe para fluxo manual.",
                    detalhes={"erro_original": str(erro)},
                )
            else:
                falha = ErroConversaoDocumento(
                    str(erro),
                    categoria="tecnico",
                    codigo="falha_tecnica_inesperada",
                    acao="Consulte os logs do conversor e tente novamente.",
                )
        processamento.status = ProcessamentoDocumento.Status.FALHOU
        processamento.metricas = {**(processamento.metricas or {}), "falha": falha.para_registro()}
        processamento.mensagem_erro = str(falha)
        processamento.concluido_em = timezone.now()
        processamento.duracao_segundos = monotonic() - inicio
        processamento.save()
        versao.documento.status = DocumentoNormativo.Status.QUARENTENA
        versao.documento.save(update_fields=["status", "atualizado_em"])
        if isinstance(erro, ErroConversaoDocumento):
            raise
        raise falha from erro
