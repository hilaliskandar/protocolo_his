from __future__ import annotations

import json
from collections import Counter

from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from .models import (
    AplicacaoMunicipal,
    ArtefatoProcessado,
    DiagnosticoPagina,
    DocumentoNormativo,
    Municipio,
    ProcessamentoDocumento,
    VersaoDocumento,
)


def inicio(request):
    processamentos = ProcessamentoDocumento.objects.select_related(
        "versao_documento",
        "versao_documento__documento",
        "versao_documento__documento__aplicacao__municipio",
    )
    contexto = {
        "total_municipios": Municipio.objects.count(),
        "total_aplicacoes": AplicacaoMunicipal.objects.count(),
        "total_documentos": DocumentoNormativo.objects.count(),
        "total_versoes": VersaoDocumento.objects.count(),
        "total_processamentos": processamentos.count(),
        "total_paginas": DiagnosticoPagina.objects.count(),
        "documentos_verificados": DocumentoNormativo.objects.filter(
            status=DocumentoNormativo.Status.VERIFICADO
        ).count(),
        "documentos_quarentena": DocumentoNormativo.objects.filter(
            status=DocumentoNormativo.Status.QUARENTENA
        ).count(),
        "paginas_ocr": DiagnosticoPagina.objects.filter(rota="ocr").count(),
        "paginas_visuais": DiagnosticoPagina.objects.filter(
            Q(mapa_suspeito=True) | Q(tabela_suspeita=True)
        ).count(),
        "aplicacoes_recentes": AplicacaoMunicipal.objects.select_related("municipio")[:5],
        "processamentos_recentes": processamentos.order_by("-criado_em")[:8],
    }
    return render(request, "applications/inicio.html", contexto)


def lista_aplicacoes(request):
    aplicacoes = (
        AplicacaoMunicipal.objects.select_related("municipio")
        .annotate(
            total_documentos=Count("documentos", distinct=True),
            total_processamentos=Count("documentos__versoes__processamentos", distinct=True),
        )
        .order_by("municipio__uf", "municipio__nome", "titulo")
    )
    return render(request, "applications/lista_aplicacoes.html", {"aplicacoes": aplicacoes})


def detalhe_aplicacao(request, pk: int):
    aplicacao = get_object_or_404(
        AplicacaoMunicipal.objects.select_related("municipio"),
        pk=pk,
    )
    documentos = (
        aplicacao.documentos.select_related("tipo")
        .prefetch_related("versoes__processamentos")
        .order_by("ano", "numero")
    )
    processamentos = ProcessamentoDocumento.objects.filter(
        versao_documento__documento__aplicacao=aplicacao
    ).select_related("versao_documento", "versao_documento__documento")
    contexto = {
        "aplicacao": aplicacao,
        "documentos": documentos,
        "total_paginas": DiagnosticoPagina.objects.filter(
            processamento__versao_documento__documento__aplicacao=aplicacao
        ).count(),
        "total_processamentos": processamentos.count(),
        "processamentos_recentes": processamentos.order_by("-criado_em")[:10],
    }
    return render(request, "applications/detalhe_aplicacao.html", contexto)


def detalhe_documento(request, pk: int):
    documento = get_object_or_404(
        DocumentoNormativo.objects.select_related("tipo", "aplicacao__municipio").prefetch_related(
            "versoes__processamentos__artefatos"
        ),
        pk=pk,
    )
    processamentos = (
        ProcessamentoDocumento.objects.filter(versao_documento__documento=documento)
        .select_related("versao_documento")
        .prefetch_related("artefatos")
        .order_by("-criado_em")
    )
    return render(
        request,
        "applications/detalhe_documento.html",
        {"documento": documento, "processamentos": processamentos},
    )


def detalhe_processamento(request, pk: int):
    processamento = get_object_or_404(
        ProcessamentoDocumento.objects.select_related(
            "versao_documento",
            "versao_documento__documento",
            "versao_documento__documento__aplicacao__municipio",
        ).prefetch_related("artefatos"),
        pk=pk,
    )
    paginas = processamento.diagnosticos_paginas.all()
    rota = request.GET.get("rota", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    avisos = request.GET.get("avisos") == "1"
    if rota:
        paginas = paginas.filter(rota=rota)
    if tipo:
        paginas = paginas.filter(tipo_pagina=tipo)
    if avisos:
        paginas = paginas.exclude(avisos=[])

    todas_paginas = list(processamento.diagnosticos_paginas.all())
    rotas = Counter(pagina.rota for pagina in todas_paginas)
    tipos = Counter(pagina.tipo_pagina for pagina in todas_paginas)
    avisos_agrupados = Counter(
        aviso for pagina in todas_paginas for aviso in (pagina.avisos or [])
    )
    contexto = {
        "processamento": processamento,
        "paginas": paginas,
        "rotas": sorted(rotas.items()),
        "tipos": sorted(tipos.items()),
        "avisos_agrupados": avisos_agrupados.most_common(),
        "filtro_rota": rota,
        "filtro_tipo": tipo,
        "filtro_avisos": avisos,
        "metricas_json": json.dumps(processamento.metricas, ensure_ascii=False, indent=2),
        "parametros_json": json.dumps(processamento.parametros, ensure_ascii=False, indent=2),
    }
    return render(request, "applications/detalhe_processamento.html", contexto)


def detalhe_pagina(request, pk: int):
    pagina = get_object_or_404(
        DiagnosticoPagina.objects.select_related(
            "processamento__versao_documento__documento__aplicacao__municipio"
        ),
        pk=pk,
    )
    contexto = {
        "pagina": pagina,
        "dados_tecnicos_json": json.dumps(
            pagina.dados_tecnicos,
            ensure_ascii=False,
            indent=2,
        ),
    }
    return render(request, "applications/detalhe_pagina.html", contexto)


def detalhe_artefato(request, pk: int):
    artefato = get_object_or_404(
        ArtefatoProcessado.objects.select_related(
            "processamento__versao_documento__documento"
        ),
        pk=pk,
    )
    conteudo = None
    conteudo_json = None
    erro_leitura = None
    if artefato.mime_type.startswith("text/") or artefato.mime_type in {
        "application/json",
        "application/x-ndjson",
    }:
        try:
            if artefato.tamanho_bytes > 5 * 1024 * 1024:
                erro_leitura = "Arquivo maior que 5 MB; use o acesso ao arquivo integral."
            else:
                with artefato.arquivo.open("rb") as arquivo:
                    conteudo = arquivo.read().decode("utf-8", errors="replace")
                if artefato.mime_type == "application/json":
                    conteudo_json = json.dumps(
                        json.loads(conteudo),
                        ensure_ascii=False,
                        indent=2,
                    )
        except (OSError, ValueError, json.JSONDecodeError) as erro:
            erro_leitura = str(erro)
    return render(
        request,
        "applications/detalhe_artefato.html",
        {
            "artefato": artefato,
            "conteudo": conteudo,
            "conteudo_json": conteudo_json,
            "erro_leitura": erro_leitura,
        },
    )


def baixar_artefato(request, pk: int):
    artefato = get_object_or_404(ArtefatoProcessado, pk=pk)
    try:
        arquivo = artefato.arquivo.open("rb")
    except OSError as erro:
        raise Http404("Artefato indisponível.") from erro
    nome = artefato.arquivo.name.rsplit("/", 1)[-1]
    return FileResponse(arquivo, as_attachment=True, filename=nome)
