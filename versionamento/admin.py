from django.contrib import admin

from .models import ClassificacaoVersao, RelacaoVersoes


@admin.register(ClassificacaoVersao)
class AdministracaoClassificacaoVersao(admin.ModelAdmin):
    list_display = (
        "versao_documento",
        "natureza",
        "data_referencia_normativa",
        "estado",
        "confirmado_por",
        "confirmado_em",
    )
    list_filter = ("natureza", "estado", "data_referencia_normativa")
    search_fields = (
        "versao_documento__nome_original",
        "versao_documento__sha256",
        "versao_documento__documento__titulo",
        "referencia_atualizacao",
        "justificativa",
    )
    autocomplete_fields = ("versao_documento", "confirmado_por")
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(RelacaoVersoes)
class AdministracaoRelacaoVersoes(admin.ModelAdmin):
    list_display = (
        "versao_origem",
        "versao_destino",
        "tipo",
        "estado",
        "validado_por",
        "validado_em",
    )
    list_filter = ("tipo", "estado")
    search_fields = (
        "versao_origem__nome_original",
        "versao_destino__nome_original",
        "versao_origem__documento__titulo",
        "versao_destino__documento__titulo",
        "justificativa",
        "fonte",
    )
    autocomplete_fields = ("versao_origem", "versao_destino", "validado_por")
    readonly_fields = ("criado_em", "atualizado_em")
