from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import FormularioImportacaoLote
from .models import ImportacaoLote
from .services import inspecionar_lote


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def nova_importacao(request):
    if request.method == "POST":
        formulario = FormularioImportacaoLote(request.POST, request.FILES)
        if formulario.is_valid():
            try:
                lote = formulario.save()
            except ValidationError as erro:
                formulario.add_error(None, erro)
            else:
                messages.success(request, "O ZIP foi recebido e registrado com rastreabilidade.")
                if formulario.cleaned_data["inspecionar_apos_envio"]:
                    try:
                        inspecionar_lote(lote)
                    except (OSError, ValueError, ValidationError) as erro:
                        messages.error(
                            request,
                            "O lote foi preservado, mas a inspeção não pôde ser concluída: "
                            f"{erro}",
                        )
                    else:
                        messages.success(
                            request,
                            "A inspeção foi concluída. Revise os itens antes da confirmação.",
                        )
                return redirect("detalhe_importacao_web", lote_id=lote.pk)
    else:
        formulario = FormularioImportacaoLote()

    return render(
        request,
        "ingestao/nova_importacao.html",
        {
            "formulario": formulario,
            "lotes_recentes": ImportacaoLote.objects.all()[:8],
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET"])
def detalhe_importacao_web(request, lote_id):
    lote = get_object_or_404(ImportacaoLote.objects.prefetch_related("itens"), pk=lote_id)
    return render(
        request,
        "ingestao/detalhe_importacao.html",
        {
            "lote": lote,
            "itens": lote.itens.all(),
        },
    )
