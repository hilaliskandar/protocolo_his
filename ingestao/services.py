from __future__ import annotations

import re
from collections import Counter
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile, ZipFile, ZipInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from applications.models import (
    AplicacaoMunicipal,
    DocumentoNormativo,
    Municipio,
    TipoNormativo,
    VersaoDocumento,
)

from .enriquecimento import diagnosticar_pdf, normalizar_numero
from .models import ImportacaoLote, ItemImportacaoLote

RE_NUMERO_ANO = [
    re.compile(
        r"(?:lei(?:[_\s-]+complementar)?|l)[_\s-]*(?:n[º°o.]?\s*)?"
        r"(\d[\d.\-]*)[_\s/-]+(\d{4})",
        re.I,
    ),
    re.compile(r"(\d[\d.]*)[_\s/-]+(\d{4})"),
]
RE_NUMERO_SEM_ANO = re.compile(
    r"(?:lei(?:[_\s-]+complementar)?|l)[_\s-]*(?:n[º°o.]?\s*)?(\d[\d.\-]*)",
    re.I,
)
PASTAS_GENERICAS = {
    "anexo",
    "anexos",
    "arquivo",
    "arquivos",
    "codigo de obras",
    "documentos",
    "legislacao",
    "leis",
    "plano diretor",
    "planos",
}


def _caminho_seguro(info: ZipInfo) -> bool:
    caminho = PurePosixPath(info.filename.replace("\\", "/"))
    return not caminho.is_absolute() and ".." not in caminho.parts


def _municipio_do_caminho(caminho: str) -> str:
    partes = PurePosixPath(caminho.replace("\\", "/")).parts[:-1]
    for parte in reversed(partes):
        candidato = parte.strip()
        normal = candidato.casefold()
        if not candidato or normal in PASTAS_GENERICAS:
            continue
        if re.match(r"^\d+\s*[-–—]", candidato) or "rm " in normal:
            continue
        return candidato
    return ""


def _natureza(nome: str) -> str:
    normal = nome.casefold()
    if "plhis" in normal:
        return ItemImportacaoLote.Natureza.PLANO_HABITACIONAL
    if "conselho" in normal:
        return ItemImportacaoLote.Natureza.PAGINA_INSTITUCIONAL
    if "fragmento" in normal:
        return ItemImportacaoLote.Natureza.FRAGMENTO_NORMATIVO
    if "anexo" in normal:
        return ItemImportacaoLote.Natureza.ANEXO_NORMATIVO
    if re.search(r"(?:^|[^0-9])2025[_-]992", normal):
        return ItemImportacaoLote.Natureza.DIARIO_OFICIAL
    if re.search(r"\bl(?:10257|13089|6766)\b", normal):
        return ItemImportacaoLote.Natureza.NORMATIVO_FEDERAL
    if "lei" in normal or re.search(r"\bl\d{4,}\b", normal):
        return ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL
    return ItemImportacaoLote.Natureza.OUTRO


def _tipo_codigo(nome: str, natureza: str) -> str:
    normativos = {
        ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL,
        ItemImportacaoLote.Natureza.NORMATIVO_FEDERAL,
    }
    if natureza not in normativos:
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
    if achado := RE_NUMERO_SEM_ANO.search(stem):
        return achado.group(1).strip(" .-_"), None
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
    fontes: dict[str, str] = {}
    if municipio:
        confianca += 0.25
        fontes["municipio_candidato"] = "estrutura_pastas"
    else:
        avisos.append("município não identificado pela estrutura de pastas")
    if tipo:
        fontes["tipo_normativo_codigo"] = "nome_arquivo"
    if numero:
        fontes["numero_candidato"] = "nome_arquivo"
    if ano:
        fontes["ano_candidato"] = "nome_arquivo"
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
    pronto = (
        natureza == ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL
        and bool(municipio and tipo and numero and ano)
        and confianca >= settings.INGESTAO_CONFIANCA_AUTOMATICA
    )
    return {
        "municipio_candidato": municipio,
        "uf": uf,
        "natureza": natureza,
        "tipo_normativo_codigo": tipo,
        "numero_candidato": numero,
        "numero_normalizado": normalizar_numero(numero),
        "ano_candidato": ano,
        "titulo_candidato": _titulo(nome),
        "fontes_metadados": fontes,
        "confianca": round(min(confianca, 1.0), 3),
        "avisos": avisos,
        "estado": ItemImportacaoLote.Estado.PRONTO if pronto else ItemImportacaoLote.Estado.REVISAO,
    }


def _registrar_divergencia(dados: dict, campo: str, aceito, sugerido) -> None:
    divergencias = list(dados.get("divergencias_metadados", []))
    divergencias.append(
        {
            "campo": campo,
            "valor_aceito": aceito,
            "valor_sugerido": sugerido,
            "fonte_aceita": dados.get("fontes_metadados", {}).get(campo, ""),
            "fonte_sugerida": "texto_primeiras_paginas",
        }
    )
    dados["divergencias_metadados"] = divergencias
    dados["estado"] = ItemImportacaoLote.Estado.REVISAO
    dados["avisos"].append(
        f"{campo.replace('_', ' ')} encontrado no texto diverge do metadado estrutural"
    )


def _aplicar_diagnostico(dados: dict, caminho_temporario: str) -> None:
    diagnostico = diagnosticar_pdf(caminho_temporario)
    dados.update(
        {
            "paginas": diagnostico.paginas or None,
            "paginas_amostradas": diagnostico.paginas_amostradas,
            "caracteres_amostra": diagnostico.caracteres_amostra,
            "rota_sugerida": diagnostico.rota_sugerida,
            "texto_amostra": diagnostico.texto_amostra,
            "numero_sugerido_texto": diagnostico.numero_texto,
            "numero_sugerido_normalizado": normalizar_numero(diagnostico.numero_texto),
            "ano_sugerido_texto": diagnostico.ano_texto,
            "fontes_sugestoes": {
                chave: "texto_primeiras_paginas"
                for chave, valor in {
                    "numero_sugerido_texto": diagnostico.numero_texto,
                    "ano_sugerido_texto": diagnostico.ano_texto,
                }.items()
                if valor
            },
            "divergencias_metadados": [],
        }
    )
    dados["avisos"] = [*dados["avisos"], *diagnostico.avisos]

    numero_aceito = dados.get("numero_candidato", "")
    numero_sugerido = diagnostico.numero_texto
    if numero_aceito and numero_sugerido:
        if normalizar_numero(numero_aceito) != normalizar_numero(numero_sugerido):
            _registrar_divergencia(dados, "numero_candidato", numero_aceito, numero_sugerido)
    elif numero_sugerido:
        dados["estado"] = ItemImportacaoLote.Estado.REVISAO
        dados["avisos"].append(
            "número sugerido pelo texto requer adjudicação humana antes da confirmação"
        )

    ano_aceito = dados.get("ano_candidato")
    ano_sugerido = diagnostico.ano_texto
    if ano_aceito and ano_sugerido:
        if ano_aceito != ano_sugerido:
            _registrar_divergencia(dados, "ano_candidato", ano_aceito, ano_sugerido)
    elif ano_sugerido:
        dados["estado"] = ItemImportacaoLote.Estado.REVISAO
        dados["avisos"].append(
            "ano sugerido pelo texto requer adjudicação humana antes da confirmação"
        )


def _itens_do_zip(lote: ImportacaoLote) -> tuple[list[ItemImportacaoLote], dict, list[str]]:
    novos: list[ItemImportacaoLote] = []
    vistos: set[str] = set()
    avisos_lote: list[str] = []
    with lote.arquivo_zip.open("rb") as arquivo, ZipFile(arquivo) as zip_file:
        infos = zip_file.infolist()
        arquivos = [(indice, info) for indice, info in enumerate(infos) if not info.is_dir()]
        if len(arquivos) > settings.INGESTAO_MAX_ARQUIVOS:
            raise ValueError("ZIP excede o limite de arquivos permitido.")
        total_descompactado = sum(info.file_size for _, info in arquivos)
        if total_descompactado > settings.INGESTAO_MAX_DESCOMPACTADO_BYTES:
            raise ValueError("ZIP excede o limite descompactado permitido.")
        for indice, info in arquivos:
            if not _caminho_seguro(info):
                avisos_lote.append(f"caminho inseguro ignorado: {info.filename}")
                continue
            if info.file_size == 0:
                avisos_lote.append(f"arquivo vazio ignorado: {info.filename}")
                continue
            razao = info.file_size / max(info.compress_size, 1)
            if razao > settings.INGESTAO_MAX_RAZAO_COMPACTACAO:
                avisos_lote.append(f"razão de compactação suspeita: {info.filename}")
                continue
            if Path(info.filename).suffix.casefold() != ".pdf":
                avisos_lote.append(f"tipo não suportado ignorado: {info.filename}")
                continue
            resumo = sha256()
            assinatura = b""
            with NamedTemporaryFile(suffix=".pdf") as temporario:
                with zip_file.open(info) as origem:
                    while bloco := origem.read(1024 * 1024):
                        if not assinatura:
                            assinatura = bloco[:5]
                        resumo.update(bloco)
                        temporario.write(bloco)
                temporario.flush()
                dados = _classificar(info.filename, lote.uf_padrao)
                assinatura_valida = assinatura == b"%PDF-"
                if assinatura_valida:
                    _aplicar_diagnostico(dados, temporario.name)
                else:
                    dados["estado"] = ItemImportacaoLote.Estado.REVISAO
                    dados["rota_sugerida"] = ItemImportacaoLote.RotaSugerida.MANUAL
                    dados["avisos"].append("assinatura do arquivo não corresponde a PDF")
            hash_item = resumo.hexdigest()
            item = ItemImportacaoLote(
                lote=lote,
                indice_arquivo=indice,
                caminho_relativo=info.filename,
                nome_original=PurePosixPath(info.filename.replace("\\", "/")).name,
                sha256=hash_item,
                tamanho_bytes=info.file_size,
                assinatura_pdf_valida=assinatura_valida,
                **dados,
            )
            if hash_item in vistos:
                item.estado = ItemImportacaoLote.Estado.DUPLICADO
                item.avisos = [*item.avisos, "conteúdo idêntico a outro item do lote"]
            else:
                vistos.add(hash_item)
            novos.append(item)
    rotas = Counter(item.rota_sugerida for item in novos)
    metricas = {
        "arquivos_zip": len(arquivos),
        "itens_pdf": len(novos),
        "bytes_descompactados": total_descompactado,
        "rotas_sugeridas": dict(rotas),
        "paginas_total": sum(item.paginas or 0 for item in novos),
    }
    return novos, metricas, avisos_lote


def _vincular_documentos_apoio(lote: ImportacaoLote) -> None:
    naturezas = [
        ItemImportacaoLote.Natureza.ANEXO_NORMATIVO,
        ItemImportacaoLote.Natureza.FRAGMENTO_NORMATIVO,
    ]
    for apoio in lote.itens.filter(natureza__in=naturezas):
        if not apoio.numero_normalizado or not apoio.ano_candidato:
            continue
        principal = (
            lote.itens.filter(
                municipio_candidato=apoio.municipio_candidato,
                natureza=ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL,
                numero_normalizado=apoio.numero_normalizado,
                ano_candidato=apoio.ano_candidato,
            )
            .exclude(pk=apoio.pk)
            .order_by("indice_arquivo")
            .first()
        )
        if principal:
            apoio.documento_principal_sugerido = principal
            apoio.save(update_fields=["documento_principal_sugerido", "atualizado_em"])


def inspecionar_lote(lote: ImportacaoLote) -> ImportacaoLote:
    if lote.status in {ImportacaoLote.Status.CONFIRMANDO, ImportacaoLote.Status.CONFIRMADO}:
        raise ValueError("Lote já está em confirmação ou foi confirmado.")
    lote.status = ImportacaoLote.Status.INSPECIONANDO
    lote.iniciado_em = timezone.now()
    lote.mensagem_erro = ""
    lote.save(update_fields=["status", "iniciado_em", "mensagem_erro", "atualizado_em"])
    try:
        novos, metricas, avisos_lote = _itens_do_zip(lote)
        with transaction.atomic():
            lote.itens.all().delete()
            ItemImportacaoLote.objects.bulk_create(novos)
            for item in lote.itens.filter(estado=ItemImportacaoLote.Estado.DUPLICADO):
                item.duplicado_de = (
                    lote.itens.filter(sha256=item.sha256)
                    .exclude(pk=item.pk)
                    .order_by("indice_arquivo")
                    .first()
                )
                item.save(update_fields=["duplicado_de", "atualizado_em"])
            _vincular_documentos_apoio(lote)
            contagem = Counter(lote.itens.values_list("estado", flat=True))
            lote.metricas = {
                **metricas,
                "prontos": contagem[ItemImportacaoLote.Estado.PRONTO],
                "revisao": contagem[ItemImportacaoLote.Estado.REVISAO],
                "duplicados": contagem[ItemImportacaoLote.Estado.DUPLICADO],
            }
            lote.avisos = avisos_lote
            lote.status = ImportacaoLote.Status.INSPECIONADO
            lote.concluido_em = timezone.now()
            lote.save(
                update_fields=["metricas", "avisos", "status", "concluido_em", "atualizado_em"]
            )
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
        defaults={
            "descricao": item.lote.descricao,
            "status": AplicacaoMunicipal.Status.CORPUS_RECEBIDO,
        },
    )
    if aplicacao.status == AplicacaoMunicipal.Status.RASCUNHO:
        aplicacao.status = AplicacaoMunicipal.Status.CORPUS_RECEBIDO
        aplicacao.save(update_fields=["status", "atualizado_em"])
    return aplicacao


def _arquivo_do_item(zip_file: ZipFile, item: ItemImportacaoLote) -> ZipInfo:
    infos = zip_file.infolist()
    if item.indice_arquivo >= len(infos):
        raise ValueError("Índice do arquivo não existe mais no ZIP original.")
    info = infos[item.indice_arquivo]
    if info.filename != item.caminho_relativo or info.file_size != item.tamanho_bytes:
        raise ValueError("O item não corresponde mais ao manifesto inspecionado.")
    return info


def _copiar_e_validar_pdf(zip_file: ZipFile, info: ZipInfo, item: ItemImportacaoLote, destino) -> None:
    resumo = sha256()
    assinatura = b""
    tamanho = 0
    with zip_file.open(info) as origem:
        while bloco := origem.read(1024 * 1024):
            if not assinatura:
                assinatura = bloco[:5]
            resumo.update(bloco)
            tamanho += len(bloco)
            destino.write(bloco)
    if assinatura != b"%PDF-" or resumo.hexdigest() != item.sha256 or tamanho != item.tamanho_bytes:
        raise ValueError("O PDF não corresponde ao hash, assinatura e tamanho inspecionados.")
    destino.flush()
    destino.seek(0)


def _materializar_item(zip_file: ZipFile, item: ItemImportacaoLote) -> VersaoDocumento:
    item.full_clean()
    info = _arquivo_do_item(zip_file, item)
    with NamedTemporaryFile(suffix=".pdf") as temporario:
        _copiar_e_validar_pdf(zip_file, info, item, temporario)
        with transaction.atomic():
            tipo = TipoNormativo.objects.get(codigo=item.tipo_normativo_codigo, ativo=True)
            aplicacao = _aplicacao_do_item(item)
            numero_documento = item.numero_normalizado or item.numero_candidato
            documento, criado = DocumentoNormativo.objects.get_or_create(
                aplicacao=aplicacao,
                tipo=tipo,
                numero=numero_documento,
                ano=item.ano_candidato,
                defaults={
                    "titulo": item.titulo_candidato,
                    "data_publicacao": item.data_publicacao_candidata,
                    "status": DocumentoNormativo.Status.RECEBIDO,
                },
            )
            if not criado and not documento.titulo and item.titulo_candidato:
                documento.titulo = item.titulo_candidato
                documento.save(update_fields=["titulo", "atualizado_em"])
            versao = documento.versoes.filter(sha256=item.sha256).first()
            if not versao:
                proxima_versao = (
                    documento.versoes.aggregate(maior=Max("versao"))["maior"] or 0
                ) + 1
                versao = VersaoDocumento(
                    documento=documento,
                    versao=proxima_versao,
                    nome_original=item.nome_original,
                    mime_type="application/pdf",
                    origem_recebimento=item.lote.origem_recebimento,
                    observacoes_ingestao=(
                        f"Importado pelo lote {item.lote.pk}; caminho: {item.caminho_relativo}; "
                        f"número informado: {item.numero_candidato}; rota sugerida: {item.rota_sugerida}"
                    ),
                )
                versao.arquivo.save(item.nome_original, File(temporario), save=True)
            item.documento_criado = documento
            item.versao_criada = versao
            item.estado = ItemImportacaoLote.Estado.CONFIRMADO
            item.save(
                update_fields=["documento_criado", "versao_criada", "estado", "atualizado_em"]
            )
    return versao


def confirmar_lote(lote: ImportacaoLote) -> dict:
    if lote.status == ImportacaoLote.Status.CONFIRMADO:
        return lote.metricas.get("confirmacao", {})
    if lote.status != ImportacaoLote.Status.INSPECIONADO:
        raise ValueError("O lote precisa estar inspecionado antes da confirmação.")
    lote.status = ImportacaoLote.Status.CONFIRMANDO
    lote.save(update_fields=["status", "atualizado_em"])
    resumo = {"confirmados": 0, "falhas": 0, "revisao": 0, "duplicados": 0}
    try:
        with lote.arquivo_zip.open("rb") as arquivo, ZipFile(arquivo) as zip_file:
            for item in lote.itens.select_related("duplicado_de").order_by("indice_arquivo"):
                if item.estado == ItemImportacaoLote.Estado.CONFIRMADO:
                    resumo["confirmados"] += 1
                    continue
                if item.estado == ItemImportacaoLote.Estado.DUPLICADO:
                    resumo["duplicados"] += 1
                    continue
                if item.estado != ItemImportacaoLote.Estado.PRONTO:
                    resumo["revisao"] += 1
                    continue
                try:
                    _materializar_item(zip_file, item)
                    resumo["confirmados"] += 1
                except (
                    TipoNormativo.DoesNotExist,
                    IntegrityError,
                    KeyError,
                    OSError,
                    ValidationError,
                    ValueError,
                ) as erro:
                    item.estado = ItemImportacaoLote.Estado.FALHOU
                    item.avisos = [*item.avisos, str(erro)]
                    item.save(update_fields=["estado", "avisos", "atualizado_em"])
                    resumo["falhas"] += 1
    except (BadZipFile, OSError, ValueError) as erro:
        lote.status = ImportacaoLote.Status.FALHOU
        lote.mensagem_erro = str(erro)
        lote.concluido_em = timezone.now()
        lote.save(update_fields=["status", "mensagem_erro", "concluido_em", "atualizado_em"])
        raise
    pendentes = lote.itens.filter(
        estado__in=[
            ItemImportacaoLote.Estado.PRONTO,
            ItemImportacaoLote.Estado.REVISAO,
            ItemImportacaoLote.Estado.FALHOU,
        ]
    ).exists()
    lote.status = (
        ImportacaoLote.Status.INSPECIONADO if pendentes else ImportacaoLote.Status.CONFIRMADO
    )
    lote.metricas = {**lote.metricas, "confirmacao": resumo}
    lote.concluido_em = timezone.now()
    lote.save(update_fields=["status", "metricas", "concluido_em", "atualizado_em"])
    return resumo
