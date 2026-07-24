from django.contrib import admin

from .models import (
    AplicacaoMunicipal,
    DocumentoNormativo,
    Municipio,
    TipoNormativo,
    VersaoDocumento,
)


@admin.register(Municipio)
class AdministracaoMunicipio(admin.ModelAdmin):
    list_display = (
        "nome",
        "uf",
        "codigo_ibge",
        "ativo",
        "possui_geometria",
        "data_referencia",
    )
    list_filter = ("uf", "ativo")
    search_fields = ("^nome", "^codigo_ibge")
    ordering = ("nome",)
    readonly_fields = (
        "nome",
        "uf",
        "codigo_ibge",
        "codigo_uf",
        "nome_uf",
        "ativo",
        "fonte_dados",
        "data_referencia",
        "sha256_fonte",
        "geometria_geojson",
        "fonte_geometria",
        "data_referencia_geometria",
        "sha256_geometria",
        "geometria_atualizada_em",
        "criado_em",
        "atualizado_em",
    )

    @admin.display(boolean=True, description="Geometria")
    def possui_geometria(self, municipio: Municipio) -> bool:
        return bool(municipio.geometria_geojson)

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(AplicacaoMunicipal)
class AdministracaoAplicacaoMunicipal(admin.ModelAdmin):
    list_display = ("titulo", "municipio", "status", "criado_em")
    list_filter = ("status", "municipio__uf")
    search_fields = ("titulo", "municipio__nome", "municipio__codigo_ibge")
    autocomplete_fields = ("municipio",)


@admin.register(TipoNormativo)
class AdministracaoTipoNormativo(admin.ModelAdmin):
    list_display = ("nome", "sigla", "esfera", "ativo", "dispositivo_fonte")
    list_filter = ("esfera", "ativo")
    search_fields = ("^nome", "^codigo", "^sigla")
    ordering = ("ordem_exibicao", "nome")
    readonly_fields = ("criado_em", "atualizado_em")


class VersaoDocumentoEmLinha(admin.TabularInline):
    model = VersaoDocumento
    extra = 0
    readonly_fields = (
        "sha256",
        "tamanho_bytes",
        "situacao_ingestao",
        "duplicado_de",
        "criado_em",
    )


@admin.register(DocumentoNormativo)
class AdministracaoDocumentoNormativo(admin.ModelAdmin):
    list_display = ("identificacao", "aplicacao", "status", "data_publicacao")
    list_filter = ("tipo", "status", "ano")
    search_fields = (
        "numero",
        "titulo",
        "aplicacao__municipio__nome",
        "tipo__nome",
    )
    autocomplete_fields = ("aplicacao", "tipo")
    inlines = (VersaoDocumentoEmLinha,)

    @admin.display(description="Documento")
    def identificacao(self, documento: DocumentoNormativo) -> str:
        return str(documento)


@admin.register(VersaoDocumento)
class AdministracaoVersaoDocumento(admin.ModelAdmin):
    list_display = (
        "documento",
        "versao",
        "nome_original",
        "situacao_ingestao",
        "tamanho_bytes",
        "criado_em",
    )
    list_filter = ("situacao_ingestao", "mime_type", "original_preservado")
    readonly_fields = (
        "sha256",
        "tamanho_bytes",
        "situacao_ingestao",
        "duplicado_de",
        "criado_em",
    )
    search_fields = ("nome_original", "sha256", "documento__titulo", "origem_recebimento")
