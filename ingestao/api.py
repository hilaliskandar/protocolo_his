from __future__ import annotations

import hmac
import json
from functools import wraps
from hashlib import sha256

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from applications.models import TipoNormativo

from .models import ImportacaoLote, ItemImportacaoLote
from .services import confirmar_lote, inspecionar_lote


def _autorizado(request: HttpRequest) -> bool:
    esperado = settings.API_INGESTAO_TOKEN
    recebido = request.headers.get("Authorization", "")
    if not esperado or not recebido.startswith("Bearer "):
        return False
    return hmac.compare_digest(recebido.removeprefix("Bearer ").strip(), esperado)


def autenticacao_api(view):
    @wraps(view)
    def interno(request: HttpRequest, *args, **kwargs):
        if not _autorizado(request):
            resposta = JsonResponse({"erro": "não autorizado"}, status=401)
            resposta["WWW-Authenticate"] = "Bearer"
            return resposta
        return view(request, *args, **kwargs)

    return interno


def _item_json(item: ItemImportacaoLote) -> dict:
    return {
        "id": item.pk,
        "indice_arquivo": item.indice_arquivo,
        "caminho_relativo": item.caminho_relativo,
        "nome_original": item.nome_original,
        "municipio_candidato": item.municipio_candidato,
        "uf": item.uf,
        "natureza": item.natureza,
        "tipo_normativo_codigo": item.tipo_normativo_codigo,
        "numero_candidato": item.numero_candidato,
        "numero_normalizado": item.numero_normalizado,
        "ano_candidato": item.ano_candidato,
        "titulo_candidato": item.titulo_candidato,
        "data_publicacao_candidata": item.data_publicacao_candidata,
        "sha256": item.sha256,
        "tamanho_bytes": item.tamanho_bytes,
        "mime_type": item.mime_type,
        "assinatura_pdf_valida": item.assinatura_pdf_valida,
        "paginas": item.paginas,
        "paginas_amostradas": item.paginas_amostradas,
        "caracteres_amostra": item.caracteres_amostra,
        "rota_sugerida": item.rota_sugerida,
        "texto_amostra": item.texto_amostra,
        "fontes_metadados": item.fontes_metadados,
        "confianca": item.confianca,
        "avisos": item.avisos,
        "estado": item.estado,
        "duplicado_de": item.duplicado_de_id,
        "documento_principal_candidato": item.documento_principal_candidato_id,
        "documento_criado": item.documento_criado_id,
        "versao_criada": item.versao_criada_id,
    }


def _lote_json(lote: ImportacaoLote, incluir_itens: bool = False) -> dict:
    dados = {
        "id": str(lote.pk),
        "titulo": lote.titulo,
        "status": lote.status,
        "nome_original": lote.nome_original,
        "sha256": lote.sha256,
        "tamanho_bytes": lote.tamanho_bytes,
        "uf_padrao": lote.uf_padrao,
        "metricas": lote.metricas,
        "avisos": lote.avisos,
        "mensagem_erro": lote.mensagem_erro,
        "criado_em": lote.criado_em.isoformat(),
        "atualizado_em": lote.atualizado_em.isoformat(),
    }
    if incluir_itens:
        dados["itens"] = [_item_json(item) for item in lote.itens.all()]
    return dados


def _hash_idempotencia(request: HttpRequest) -> str | None:
    chave = request.headers.get("Idempotency-Key", "").strip()
    if not chave:
        return None
    if len(chave) > 200:
        raise ValidationError({"Idempotency-Key": "A chave deve ter no máximo 200 caracteres."})
    return sha256(chave.encode("utf-8")).hexdigest()


@csrf_exempt
@autenticacao_api
@require_http_methods(["POST"])
def criar_importacao(request: HttpRequest) -> JsonResponse:
    try:
        chave_hash = _hash_idempotencia(request)
    except ValidationError as erro:
        return JsonResponse({"erro": erro.message_dict}, status=400)
    if chave_hash:
        existente = ImportacaoLote.objects.filter(chave_idempotencia_sha256=chave_hash).first()
        if existente:
            dados = _lote_json(existente)
            dados["reutilizado"] = True
            return JsonResponse(dados, status=200)
    arquivo = request.FILES.get("arquivo_zip")
    if arquivo is None:
        return JsonResponse({"erro": "campo arquivo_zip é obrigatório"}, status=400)
    if arquivo.size > settings.INGESTAO_MAX_ZIP_BYTES:
        return JsonResponse({"erro": "arquivo ZIP excede o limite configurado"}, status=413)
    if not arquivo.name.casefold().endswith(".zip"):
        return JsonResponse({"erro": "arquivo_zip deve possuir extensão .zip"}, status=400)
    posicao = arquivo.tell()
    assinatura = arquivo.read(4)
    arquivo.seek(posicao)
    if assinatura[:2] != b"PK":
        return JsonResponse({"erro": "assinatura do arquivo não corresponde a ZIP"}, status=400)
    titulo = request.POST.get("titulo", "").strip()
    origem = request.POST.get("origem_recebimento", "").strip()
    if not titulo or not origem:
        return JsonResponse({"erro": "titulo e origem_recebimento são obrigatórios"}, status=400)
    lote = ImportacaoLote(
        titulo=titulo,
        descricao=request.POST.get("descricao", "").strip(),
        origem_recebimento=origem,
        uf_padrao=request.POST.get("uf_padrao", "SP"),
        arquivo_zip=arquivo,
        nome_original=arquivo.name,
        chave_idempotencia_sha256=chave_hash,
        parametros={"dry_run": True},
    )
    try:
        lote.full_clean(exclude=["sha256", "tamanho_bytes"])
        lote.save()
    except IntegrityError:
        if chave_hash:
            existente = ImportacaoLote.objects.filter(chave_idempotencia_sha256=chave_hash).first()
            if existente:
                dados = _lote_json(existente)
                dados["reutilizado"] = True
                return JsonResponse(dados, status=200)
        return JsonResponse({"erro": "conflito ao registrar o lote"}, status=409)
    except ValidationError as erro:
        return JsonResponse({"erro": erro.message_dict}, status=400)
    return JsonResponse(_lote_json(lote), status=201)


@autenticacao_api
@require_http_methods(["GET"])
def detalhe_importacao(request: HttpRequest, lote_id) -> JsonResponse:
    lote = get_object_or_404(ImportacaoLote, pk=lote_id)
    return JsonResponse(_lote_json(lote, incluir_itens=request.GET.get("itens") == "1"))


@csrf_exempt
@autenticacao_api
@require_http_methods(["POST"])
def inspecionar_importacao(request: HttpRequest, lote_id) -> JsonResponse:
    lote = get_object_or_404(ImportacaoLote, pk=lote_id)
    try:
        inspecionar_lote(lote)
    except (OSError, ValueError) as erro:
        return JsonResponse({"erro": str(erro), "lote": _lote_json(lote)}, status=422)
    return JsonResponse(_lote_json(lote, incluir_itens=True))


@autenticacao_api
@require_http_methods(["GET"])
def listar_itens(request: HttpRequest, lote_id) -> JsonResponse:
    lote = get_object_or_404(ImportacaoLote, pk=lote_id)
    return JsonResponse(
        {"lote": str(lote.pk), "itens": [_item_json(item) for item in lote.itens.all()]}
    )


@csrf_exempt
@autenticacao_api
@require_http_methods(["PATCH"])
def atualizar_item(request: HttpRequest, item_id: int) -> JsonResponse:
    item = get_object_or_404(ItemImportacaoLote, pk=item_id)
    try:
        dados = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"erro": "JSON inválido"}, status=400)
    if not isinstance(dados, dict):
        return JsonResponse({"erro": "o corpo JSON deve ser um objeto"}, status=400)
    campos = {
        "municipio_candidato",
        "uf",
        "natureza",
        "tipo_normativo_codigo",
        "numero_candidato",
        "ano_candidato",
        "titulo_candidato",
        "data_publicacao_candidata",
        "documento_principal_candidato",
        "estado",
    }
    desconhecidos = set(dados) - campos
    if desconhecidos:
        return JsonResponse({"erro": f"campos não permitidos: {sorted(desconhecidos)}"}, status=400)
    tipo_codigo = dados.get("tipo_normativo_codigo")
    if tipo_codigo and not TipoNormativo.objects.filter(codigo=tipo_codigo, ativo=True).exists():
        return JsonResponse({"erro": "tipo_normativo_codigo inexistente ou inativo"}, status=400)
    principal_id = dados.pop("documento_principal_candidato", None)
    if principal_id is not None:
        principal = get_object_or_404(ItemImportacaoLote, pk=principal_id)
        if principal.lote_id != item.lote_id or principal.pk == item.pk:
            return JsonResponse({"erro": "documento principal deve pertencer ao mesmo lote"}, status=400)
        item.documento_principal_candidato = principal
    for campo, valor in dados.items():
        setattr(item, campo, valor)
    if item.estado == ItemImportacaoLote.Estado.PRONTO:
        obrigatorios = [
            item.municipio_candidato,
            item.uf,
            item.tipo_normativo_codigo,
            item.numero_candidato,
            item.ano_candidato,
            item.titulo_candidato,
        ]
        if item.natureza != ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL or not all(
            obrigatorios
        ):
            return JsonResponse(
                {"erro": "item pronto exige metadados completos de ato municipal"}, status=400
            )
    try:
        item.full_clean()
        item.save()
    except ValidationError as erro:
        return JsonResponse({"erro": erro.message_dict}, status=400)
    return JsonResponse(_item_json(item))


@csrf_exempt
@autenticacao_api
@require_http_methods(["POST"])
def confirmar_importacao(request: HttpRequest, lote_id) -> JsonResponse:
    lote = get_object_or_404(ImportacaoLote, pk=lote_id)
    try:
        resumo = confirmar_lote(lote)
    except ValueError as erro:
        return JsonResponse({"erro": str(erro)}, status=409)
    return JsonResponse({"lote": _lote_json(lote), "resumo": resumo})
