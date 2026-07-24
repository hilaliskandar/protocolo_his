from django.shortcuts import render

from .models import AplicacaoMunicipal, DocumentoNormativo, Municipio, VersaoDocumento


def inicio(request):
    contexto = {
        "total_municipios": Municipio.objects.count(),
        "total_aplicacoes": AplicacaoMunicipal.objects.count(),
        "total_documentos": DocumentoNormativo.objects.count(),
        "total_versoes": VersaoDocumento.objects.count(),
        "aplicacoes_recentes": AplicacaoMunicipal.objects.select_related("municipio")[:5],
    }
    return render(request, "applications/inicio.html", contexto)
