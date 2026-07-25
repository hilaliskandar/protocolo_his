from django.urls import path

from .views import (
    baixar_artefato,
    detalhe_aplicacao,
    detalhe_artefato,
    detalhe_documento,
    detalhe_pagina,
    detalhe_processamento,
    exibir_pdf,
    inicio,
    leitor_documento,
    lista_aplicacoes,
)

urlpatterns = [
    path("", inicio, name="inicio"),
    path("aplicacoes/", lista_aplicacoes, name="lista_aplicacoes"),
    path("aplicacoes/<int:pk>/", detalhe_aplicacao, name="detalhe_aplicacao"),
    path("documentos/<int:pk>/", detalhe_documento, name="detalhe_documento"),
    path("documentos/<int:pk>/leitor/", leitor_documento, name="leitor_documento"),
    path("versoes/<int:pk>/pdf/", exibir_pdf, name="exibir_pdf"),
    path("processamentos/<int:pk>/", detalhe_processamento, name="detalhe_processamento"),
    path("paginas/<int:pk>/", detalhe_pagina, name="detalhe_pagina"),
    path("artefatos/<int:pk>/", detalhe_artefato, name="detalhe_artefato"),
    path("artefatos/<int:pk>/baixar/", baixar_artefato, name="baixar_artefato"),
]
