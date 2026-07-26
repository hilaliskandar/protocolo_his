from django.urls import path

from .api import (
    atualizar_item,
    confirmar_importacao,
    criar_importacao,
    detalhe_importacao,
    inspecionar_importacao,
    listar_itens,
)

urlpatterns = [
    path("importacoes/", criar_importacao, name="api_criar_importacao"),
    path("importacoes/<uuid:lote_id>/", detalhe_importacao, name="api_detalhe_importacao"),
    path("importacoes/<uuid:lote_id>/inspecionar/", inspecionar_importacao, name="api_inspecionar_importacao"),
    path("importacoes/<uuid:lote_id>/itens/", listar_itens, name="api_listar_itens_importacao"),
    path("importacoes/<uuid:lote_id>/confirmar/", confirmar_importacao, name="api_confirmar_importacao"),
    path("itens-importacao/<int:item_id>/", atualizar_item, name="api_atualizar_item_importacao"),
]
