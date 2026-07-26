from django.contrib import admin

from .models import ImportacaoLote, ItemImportacaoLote


class ItemImportacaoEmLinha(admin.TabularInline):
    model = ItemImportacaoLote
    extra = 0
    fields = (
        "nome_original",
        "municipio_candidato",
        "natureza",
        "tipo_normativo_codigo",
        "numero_candidato",
        "ano_candidato",
        "rota_sugerida",
        "confianca",
        "estado",
    )
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(ImportacaoLote)
class AdministracaoImportacaoLote(admin.ModelAdmin):
    list_display = ("titulo", "status", "nome_original", "tamanho_bytes", "criado_em")
    list_filter = ("status", "uf_padrao")
    search_fields = ("titulo", "nome_original", "sha256", "origem_recebimento")
    readonly_fields = (
        "sha256",
        "tamanho_bytes",
        "status",
        "parametros",
        "metricas",
        "avisos",
        "mensagem_erro",
        "criado_em",
        "atualizado_em",
        "iniciado_em",
        "concluido_em",
    )
    inlines = (ItemImportacaoEmLinha,)


@admin.register(ItemImportacaoLote)
class AdministracaoItemImportacaoLote(admin.ModelAdmin):
    list_display = (
        "nome_original",
        "municipio_candidato",
        "natureza",
        "numero_candidato",
        "ano_candidato",
        "rota_sugerida",
        "confianca",
        "estado",
    )
    list_filter = ("estado", "natureza", "rota_sugerida", "uf")
    search_fields = ("nome_original", "caminho_relativo", "sha256", "municipio_candidato")
    readonly_fields = (
        "lote",
        "caminho_relativo",
        "nome_original",
        "numero_normalizado",
        "numero_sugerido_texto",
        "numero_sugerido_normalizado",
        "ano_sugerido_texto",
        "fontes_sugestoes",
        "divergencias_metadados",
        "sha256",
        "tamanho_bytes",
        "mime_type",
        "assinatura_pdf_valida",
        "paginas",
        "paginas_amostradas",
        "caracteres_amostra",
        "rota_sugerida",
        "texto_amostra",
        "fontes_metadados",
        "confianca",
        "avisos",
        "duplicado_de",
        "documento_principal_sugerido",
        "documento_criado",
        "versao_criada",
        "criado_em",
        "atualizado_em",
    )
