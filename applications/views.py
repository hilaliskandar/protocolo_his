from __future__ import annotations

import json
from collections import Counter

from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from markdown_it import MarkdownIt

from .models import (
    AplicacaoMunicipal,
    ArtefatoProcessado,
    DiagnosticoPagina,
    DocumentoNormativo,
    Municipio,
    ProcessamentoDocumento,
    VersaoDocumento,
)

LIMITE_VISUALIZACAO_TEXTO = 5 * 1024 * 1024
MODOS_LEITOR = {"pdf", "markdown", "comparacao"}


def _ler_arquivo_textual(artefato: ArtefatoProcessado) -> tuple[str | None, str | None]:
    if artefato.tamanho_bytes > LIMITE_VISUALIZACAO_TEXTO:
        return None, "Arquivo maior que 5 MB; use o acesso ao arquivo integral."
    try:
        with artefato.arquivo.open("rb") as arquivo:
            return arquivo.read().decode("utf-8", errors="replace"), None
    except OSError as erro:
        return None, str(erro)


def _renderizar_markdown_seguro(conteudo: str) -> str:
    renderizador = MarkdownIt(
        "commonmark",
        {"html": False, "linkify": False, "typographer": False},
    )
    return renderizador.render(conteudo)


def inicio(request):
    processamentos = ProcessamentoDocumento.objects.select_related(
        "versao_documento",
        "versao_documento__documento",
        "versao_documento__documento__aplicacao__municipio",
    )
    contexto = {
        "total_municipios": Municipio.objects.filter(
            aplicacoes__documentos__isnull=False
        ).distinct().count(),
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


def leitor_documento(request, pk: int):
    documento = get_object_or_404(
        DocumentoNormativo.objects.select_related("tipo", "aplicacao__municipio").prefetch_related(
            "versoes__processamentos__artefatos"
        ),
        pk=pk,
    )
    modo = request.GET.get("modo", "pdf").strip().lower()
    if modo not in MODOS_LEITOR:
        modo = "pdf"

    versao = documento.versoes.order_by("-versao", "-criado_em").first()
    artefato_markdown = (
        ArtefatoProcessado.objects.filter(
            processamento__versao_documento__documento=documento,
            processamento__status=ProcessamentoDocumento.Status.CONCLUIDO,
            tipo=ArtefatoProcessado.Tipo.MARKDOWN,
        )
        .select_related("processamento")
        .order_by("-criado_em", "-pk")
        .first()
    )

    markdown_html = None
    markdown_bruto = None
    erro_markdown = None
    if artefato_markdown:
        markdown_bruto, erro_markdown = _ler_arquivo_textual(artefato_markdown)
        if markdown_bruto is not None:
            markdown_html = _renderizar_markdown_seguro(markdown_bruto)

    contexto = {
        "documento": documento,
        "versao": versao,
        "modo": modo,
        "artefato_markdown": artefato_markdown,
        "markdown_html": markdown_html,
        "markdown_bruto": markdown_bruto,
        "erro_markdown": erro_markdown,
        "pdf_disponivel": bool(versao and versao.arquivo),
        "markdown_disponivel": markdown_html is not None,
    }
    return render(request, "applications/leitor_documento.html", contexto)


def exibir_pdf(request, pk: int):
    versao = get_object_or_404(VersaoDocumento.objects.select_related("documento"), pk=pk)
    if versao.mime_type and versao.mime_type != "application/pdf":
        raise Http404("A versão selecionada não é um PDF.")
    try:
        arquivo = versao.arquivo.open("rb")
    except OSError as erro:
        raise Http404("PDF indisponível.") from erro
    nome = versao.nome_original or versao.arquivo.name.rsplit("/", 1)[-1]
    resposta = FileResponse(arquivo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


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
        conteudo, erro_leitura = _ler_arquivo_textual(artefato)
        if conteudo is not None and artefato.mime_type == "application/json":
            try:
                conteudo_json = json.dumps(
                    json.loads(conteudo),
                    ensure_ascii=False,
                    indent=2,
                )
            except json.JSONDecodeError as erro:
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
