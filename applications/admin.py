from django.contrib import admin

from .models import AplicacaoMunicipal, DocumentoNormativo, Municipio, VersaoDocumento


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ("nome", "uf", "codigo_ibge", "criado_em")
    list_filter = ("uf",)
    search_fields = ("nome", "codigo_ibge")


@admin.register(AplicacaoMunicipal)
class AplicacaoMunicipalAdmin(admin.ModelAdmin):
    list_display = ("titulo", "municipio", "status", "criado_em")
    list_filter = ("status", "municipio__uf")
    search_fields = ("titulo", "municipio__nome")


class VersaoDocumentoInline(admin.TabularInline):
    model = VersaoDocumento
    extra = 0
    readonly_fields = ("sha256", "tamanho_bytes", "criado_em")


@admin.register(DocumentoNormativo)
class DocumentoNormativoAdmin(admin.ModelAdmin):
    list_display = ("identificacao", "aplicacao", "status", "data_publicacao")
    list_filter = ("tipo", "status", "ano")
    search_fields = ("numero", "titulo", "aplicacao__municipio__nome")
    inlines = (VersaoDocumentoInline,)

    @admin.display(description="Documento")
    def identificacao(self, obj: DocumentoNormativo) -> str:
        return str(obj)


@admin.register(VersaoDocumento)
class VersaoDocumentoAdmin(admin.ModelAdmin):
    list_display = ("documento", "versao", "nome_original", "tamanho_bytes", "criado_em")
    readonly_fields = ("sha256", "tamanho_bytes", "criado_em")
    search_fields = ("nome_original", "sha256", "documento__titulo")
