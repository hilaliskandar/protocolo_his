from django.urls import path

from .views_interface import (
    detalhe_importacao_web,
    inspecionar_importacao_web,
    nova_importacao,
)

urlpatterns = [
    path("nova/", nova_importacao, name="nova_importacao"),
    path("<uuid:lote_id>/", detalhe_importacao_web, name="detalhe_importacao_web"),
    path(
        "<uuid:lote_id>/inspecionar/",
        inspecionar_importacao_web,
        name="inspecionar_importacao_web",
    ),
]
