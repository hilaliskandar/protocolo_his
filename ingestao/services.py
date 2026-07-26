from __future__ import annotations

import re
import shutil
from collections import Counter
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile, ZipFile, ZipInfo

from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from applications.models import AplicacaoMunicipal, DocumentoNormativo, Municipio, TipoNormativo, VersaoDocumento

from .models import ImportacaoLote, ItemImportacaoLote

RE_NUMERO_ANO = [
    re.compile(r"(?:lei(?:[_\s-]+complementar)?|l)[_\s-]*(\d[\d.\-]*)[_\s/-]+(\d{4})", re.I),
    re.compile(r"(\d[\d.]*)[_\s/-]+(\d{4})"),
]


def _caminho_seguro(info: ZipInfo) -> bool:
    caminho = PurePosixPath(info.filename.replace("\\", "/"))
    return not caminho.is_absolute() and ".." not in caminho.parts


def _municipio_do_caminho(caminho: str) -> str:
    partes = PurePosixPath(caminho.replace("\\", "/")).parts
    return partes[-2].strip() if len(partes) >= 2 else ""


def _natureza(nome: str) -> str:
    normal = nome.casefold()
    if "plhis" in normal:
        return ItemImportacaoLote.Natureza.PLANO_HABITACIONAL
    if "conselho" in normal:
        return ItemImportacaoLote.Natureza.PAGINA_INSTITUCIONAL
    if "fragmento" in normal:
        return ItemImportacaoLote.Natureza.FRAGMENTO_NORMATIVO
    if "anexo" in normal or "anexos" in normal:
        return ItemImportacaoLote.Natureza.ANEXO_NORMATIVO
    if re.search(r"(?:^|[^0-9])2025[_-]992", normal):
        return ItemImportacaoLote.Natureza.DIARIO_OFICIAL
    if re.search(r"\bl(?:10257|13089|6766)\b", normal):
        return ItemImportacaoLote.Natureza.NORMATIVO_FEDERAL
    if "lei" in normal or re.search(r"\bl\d{4,}\b", normal):
        return ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL
    return ItemImportacaoLote.Natureza.OUTRO


def _tipo_codigo(nome: str, natureza: str) -> str:
    if natureza not in {ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL, ItemImportacaoLote.Natureza.NORMATIVO_FEDERAL}:
        return ""
    normal = nome.casefold()
    if "lei complementar" in normal or "lei_complementar" in normal:
        return "lei_complementar"
    if "lei organica" in normal or "lei-orgânica" in normal or "lei-organica" in normal:
        return "lei_organica"
    return "lei_ordinaria"


def _numero_ano(nome: str) -> tuple[str, int | None]:
    stem = Path(nome).stem
    for padrao in RE_NUMERO_ANO:
        if achado := padrao.search(stem):
            numero = achado.group(1).strip(" .-_")
            ano = int(achado.group(2))
            if 1800 <= ano <= 2200:
                return numero, ano
    return "", None


def _titulo(nome: str) -> str:
    return re.sub(r"\s+", " ", Path(nome).stem.replace("_", " ")).strip()[:255]


def _classificar(caminho: str, uf: str) -> dict:
    nome = PurePosixPath(caminho.replace("\\", "/")).name
    municipio = _municipio_do_caminho(caminho)
    natureza = _natureza(nome)
    tipo = _tipo_codigo(nome, natureza)
    numero, ano = _numero_ano(nome)
    confianca = 0.20
    avisos: list[str] = []
    if municipio:
        confianca += 0.25
    else:
        avisos.append("município não identificado pela estrutura de pastas")
    if natureza == ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL:
        confianca += 0.15
        if tipo:
            confianca += 0.10
        if numero:
            confianca += 0.15
        else:
            avisos.append("número do ato não identificado")
        if ano:
            confianca += 0.15
        else:
            avisos.append("ano do ato não identificado")
    else:
        avisos.append("natureza documental exige adjudicação antes da criação de ato municipal")
    pronto = natureza == ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL and bool(municipio and tipo and numero and ano) and confianca >= settings.INGESTAO_CONFIANCA_AUTOMATICA
    return {
        "municipio_candidato": municipio,
        "uf": uf,
        "natureza": natureza,
        "tipo_normativo_codigo": tipo,
        "numero_candidato": numero,
        "ano_candidato": ano,
        "titulo_candidato": _titulo(nome),
        "confianca": round(min(confianca, 1.0), 3),
        "avisos": avisos,
        "estado": ItemImportacaoLote.Estado.PRONTO if pronto else ItemImportacaoLote.Estado.REVISAO,
    }


def inspecionar_lote(lote: ImportacaoLote) -> ImportacaoLote:
    if lote.status in {ImportacaoLote.Status.CONFIRMANDO, ImportacaoLote.Status.CONFIRMADO}:
        raise ValueError("Lote já está em confirmação ou foi confirmado.")
    lote.status = ImportacaoLote.Status.INSPECIONANDO
    lote.iniciado_em = timezone.now()
    lote.mensagem_erro = ""
    lote.save(update_fields=["status", "iniciado_em", "mensagem_erro", "atualizado_em"])
    lote.itens.all().delete()
    try:
        with lote.arquivo_zip.open("rb") as arquivo, ZipFile(arquivo) as zip_file:
            infos = [info for info in zip_file.infolist() if not info.is_dir()]
            if len(infos) > settings.INGESTAO_MAX_ARQUIVOS:
                raise ValueError("ZIP excede o limite de arquivos permitido.")
            total_descompactado = sum(info.file_size for info in infos)
            if total_descompactado > settings.INGESTAO_MAX_DESCOMPACTADO_BYTES:
                raise ValueError("ZIP excede o limite descompactado permitido.")
            vistos: dict[str, ItemImportacaoLote] = {}
            avisos_lote: list[str] = []
            for info in infos:
                if not _caminho_seguro(info):
                    avisos_lote.append(f"caminho inseguro ignorado: {info.filename}")
                    continue
                if info.file_size == 0:
                    avisos_lote.append(f"arquivo vazio ignorado: {info.filename}")
                    continue
                if info.compress_size and info.file_size / info.compress_size > settings.INGESTAO_MAX_RAZAO_COMPACTACAO:
                    avisos_lote.append(f"razão de compactação suspeita: {info.filename}")
                    continue
                if Path(info.filename).suffix.casefold() != ".pdf":
                    avisos_lote.append(f"tipo não suportado ignorado: {info.filename}")
                    continue
                resumo = sha256()
                assinatura = b""
                with zip_file.open(info) as origem:
                    while bloco := origem.read(1024 * 1024):
                        if not assinatura:
                            assinatura = bloco[:5]
                        resumo.update(bloco)
                dados = _classificar(info.filename, lote.uf_padrao)
                if assinatura != b"%PDF-":
                    dados["estado"] = ItemImportacaoLote.Estado.REVISAO
                    dados["avisos"].append("assinatura do arquivo não corresponde a PDF")
                hash_item = resumo.hexdigest()
                item = ItemImportacaoLote.objects.create(lote=lote, caminho_relativo=info.filename, nome_original=PurePosixPath(info.filename.replace("\\", "/")).name, sha256=hash_item, tamanho_bytes=info.file_size, **dados)
                if hash_item in vistos:
                    item.estado = ItemImportacaoLote.Estado.DUPLICADO
                    item.duplicado_de = vistos[hash_item]
                    item.avisos = [*item.avisos, "conteúdo idêntico a outro item do lote"]
                    item.save(update_fields=["estado", "duplicado_de", "avisos", "atualizado_em"])
                else:
                    vistos[hash_item] = item
            contagem = Counter(lote.itens.values_list("estado", flat=True))
            lote.metricas = {"arquivos_zip": len(infos), "itens_pdf": lote.itens.count(), "bytes_descompactados": total_descompactado, "prontos": contagem[ItemImportacaoLote.Estado.PRONTO], "revisao": contagem[ItemImportacaoLote.Estado.REVISAO], "duplicados": contagem[ItemImportacaoLote.Estado.DUPLICADO]}
            lote.avisos = avisos_lote
            lote.status = ImportacaoLote.Status.INSPECIONADO
            lote.concluido_em = timezone.now()
            lote.save(update_fields=["metricas", "avisos", "status", "concluido_em", "atualizado_em"])
            return lote
    except (BadZipFile, OSError, ValueError) as erro:
        lote.status = ImportacaoLote.Status.FALHOU
        lote.mensagem_erro = str(erro)
        lote.concluido_em = timezone.now()
        lote.save(update_fields=["status", "mensagem_erro", "concluido_em", "atualizado_em"])
        raise


def _aplicacao_do_item(item: ItemImportacaoLote) -> AplicacaoMunicipal:
    municipio, _ = Municipio.objects.get_or_create(nome=item.municipio_candidato, uf=item.uf)
    aplicacao, _ = AplicacaoMunicipal.objects.get_or_create(
        municipio=municipio,
        titulo=f"{item.lote.titulo} — {municipio.nome}",
        defaults={"descricao": item.lote.descricao, "status": AplicacaoMunicipal.Status.CORPUS_RECEBIDO},
    )
    if aplicacao.status == AplicacaoMunicipal.Status.RASCUNHO:
        aplicacao.status = AplicacaoMunicipal.Status.CORPUS_RECEBIDO
        aplicacao.save(update_fields=["status", "atualizado_em"])
    return aplicacao


def confirmar_lote(lote: ImportacaoLote) -> dict:
    if lote.status != ImportacaoLote.Status.INSPECIONADO:
        raise ValueError("O lote precisa estar inspecionado antes da confirmação.")
    lote.status = ImportacaoLote.Status.CONFIRMANDO
    lote.save(update_fields=["status", "atualizado_em"])
    resumo = {"confirmados": 0, "falhas": 0, "revisao": 0, "duplicados": 0}
    with lote.arquivo_zip.open("rb") as arquivo, ZipFile(arquivo) as zip_file:
        for item in lote.itens.select_related("duplicado_de").order_by("pk"):
            if item.estado == ItemImportacaoLote.Estado.DUPLICADO:
                resumo["duplicados"] += 1
                continue
            if item.estado != ItemImportacaoLote.Estado.PRONTO:
                resumo["revisao"] += 1
                continue
            try:
                with transaction.atomic():
                    tipo = TipoNormativo.objects.get(codigo=item.tipo_normativo_codigo, ativo=True)
                    aplicacao = _aplicacao_do_item(item)
                    documento, criado = DocumentoNormativo.objects.get_or_create(
                        aplicacao=aplicacao,
                        tipo=tipo,
                        numero=item.numero_candidato,
                        ano=item.ano_candidato,
                        defaults={"titulo": item.titulo_candidato, "data_publicacao": item.data_publicacao_candidata, "status": DocumentoNormativo.Status.RECEBIDO},
                    )
                    if not criado and not documento.titulo and item.titulo_candidato:
                        documento.titulo = item.titulo_candidato
                        documento.save(update_fields=["titulo", "atualizado_em"])
                    proxima_versao = (documento.versoes.aggregate(maior=Max("versao"))["maior"] or 0) + 1
                    with NamedTemporaryFile(suffix=".pdf") as temporario:
                        with zip_file.open(item.caminho_relativo) as origem:
                            shutil.copyfileobj(origem, temporario)
                        temporario.flush()
                        temporario.seek(0)
                        versao = VersaoDocumento(documento=documento, versao=proxima_versao, nome_original=item.nome_original, mime_type="application/pdf", origem_recebimento=lote.origem_recebimento, observacoes_ingestao=f"Importado pelo lote {lote.pk}; caminho: {item.caminho_relativo}")
                        versao.arquivo.save(item.nome_original, File(temporario), save=True)
                    item.documento_criado = documento
                    item.versao_criada = versao
                    item.estado = ItemImportacaoLote.Estado.CONFIRMADO
                    item.save(update_fields=["documento_criado", "versao_criada", "estado", "atualizado_em"])
                    resumo["confirmados"] += 1
            except (TipoNormativo.DoesNotExist, KeyError, OSError, ValueError) as erro:
                item.estado = ItemImportacaoLote.Estado.FALHOU
                item.avisos = [*item.avisos, str(erro)]
                item.save(update_fields=["estado", "avisos", "atualizado_em"])
                resumo["falhas"] += 1
    lote.status = ImportacaoLote.Status.CONFIRMADO if resumo["falhas"] == 0 else ImportacaoLote.Status.INSPECIONADO
    lote.metricas = {**lote.metricas, "confirmacao": resumo}
    lote.concluido_em = timezone.now()
    lote.save(update_fields=["status", "metricas", "concluido_em", "atualizado_em"])
    return resumo
