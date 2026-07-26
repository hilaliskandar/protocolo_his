from __future__ import annotations

import hmac
import json
from functools import wraps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from applications.models import TipoNormativo

from .models import ImportacaoLote, ItemImportacaoLote
from .services import confirmar_lote, inspecionar_lote


def _autorizado(request: HttpRequest) -> bool:
    if request.user.is_authenticated and request.user.is_staff:
        return True
    esperado = settings.API_INGESTAO_TOKEN
    recebido = request.headers.get("Authorization", "")
    if not esperado or not recebido.startswith("Bearer "):
        return False
    return hmac.compare_digest(recebido.removeprefix("Bearer ").strip(), esperado)


def autenticacao_api(view):
    @wraps(view)
    def interno(request: HttpRequest, *args, **kwargs):
        if not _autorizado(request):
            return JsonResponse({"erro": "não autorizado"}, status=401)
        return view(request, *args, **kwargs)

    return interno


def _item_json(item: ItemImportacaoLote) -> dict:
    return {
        "id": item.pk,
        "caminho_relativo": item.caminho_relativo,
        "nome_original": item.nome_original,
        "municipio_candidato": item.municipio_candidato,
        "uf": item.uf,
        "natureza": item.natureza,
        "tipo_normativo_codigo": item.tipo_normativo_codigo,
        "numero_candidato": item.numero_candidato,
        "ano_candidato": item.ano_candidato,
        "titulo_candidato": item.titulo_candidato,
        "data_publicacao_candidata": item.data_publicacao_candidata,
        "sha256": item.sha256,
        "tamanho_bytes": item.tamanho_bytes,
        "mime_type": item.mime_type,
        "confianca": item.confianca,
        "avisos": item.avisos,
        "estado": item.estado,
        "duplicado_de": item.duplicado_de_id,
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


@csrf_exempt
@autenticacao_api
@require_http_methods(["POST"])
def criar_importacao(request: HttpRequest) -> JsonResponse:
    arquivo = request.FILES.get("arquivo_zip")
    if arquivo is None:
        return JsonResponse({"erro": "campo arquivo_zip é obrigatório"}, status=400)
    if arquivo.size > settings.INGESTAO_MAX_ZIP_BYTES:
        return JsonResponse({"erro": "arquivo ZIP excede o limite configurado"}, status=413)
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
        parametros={"dry_run": True},
    )
    try:
        lote.full_clean(exclude=["sha256", "tamanho_bytes"])
        lote.save()
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
    campos = {
        "municipio_candidato",
        "uf",
        "natureza",
        "tipo_normativo_codigo",
        "numero_candidato",
        "ano_candidato",
        "titulo_candidato",
        "data_publicacao_candidata",
        "confianca",
        "avisos",
        "estado",
    }
    desconhecidos = set(dados) - campos
    if desconhecidos:
        return JsonResponse({"erro": f"campos não permitidos: {sorted(desconhecidos)}"}, status=400)
    tipo_codigo = dados.get("tipo_normativo_codigo")
    if tipo_codigo and not TipoNormativo.objects.filter(codigo=tipo_codigo, ativo=True).exists():
        return JsonResponse({"erro": "tipo_normativo_codigo inexistente ou inativo"}, status=400)
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
