from django.contrib import admin

from .models import (
    AdjudicacaoDocumental,
    AnexoNormativo,
    AplicacaoMunicipal,
    ArtefatoProcessado,
    ArtigoNormativo,
    ContextoNormativoC0,
    AtoNormativo,
    DiagnosticoPagina,
    DocumentoNormativo,
    LeituraIntegral,
    LivroCobertura,
    Municipio,
    OcorrenciaDocumental,
    ProcessamentoDocumento,
    ReleaseCorpus,
    ReleaseCorpusDocumento,
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


class DiagnosticoPaginaEmLinha(admin.TabularInline):
    model = DiagnosticoPagina
    extra = 0
    can_delete = False
    fields = (
        "numero_pagina",
        "rota",
        "tipo_pagina",
        "possui_texto_nativo",
        "quantidade_caracteres",
        "quantidade_imagens",
        "tabela_suspeita",
        "mapa_suspeito",
    )
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None) -> bool:
        return False


class ArtefatoProcessadoEmLinha(admin.TabularInline):
    model = ArtefatoProcessado
    extra = 0
    can_delete = False
    readonly_fields = (
        "tipo",
        "arquivo",
        "sha256",
        "tamanho_bytes",
        "mime_type",
        "criado_em",
    )

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(ProcessamentoDocumento)
class AdministracaoProcessamentoDocumento(admin.ModelAdmin):
    list_display = (
        "versao_documento",
        "etapa",
        "status",
        "rota_documento",
        "ferramenta",
        "versao_ferramenta",
        "criado_em",
    )
    list_filter = ("etapa", "status", "rota_documento", "ferramenta")
    search_fields = (
        "versao_documento__nome_original",
        "versao_documento__documento__titulo",
        "versao_documento__sha256",
    )
    readonly_fields = (
        "versao_documento",
        "etapa",
        "status",
        "rota_documento",
        "ferramenta",
        "versao_ferramenta",
        "versao_codigo",
        "parametros",
        "metricas",
        "avisos",
        "mensagem_erro",
        "iniciado_em",
        "concluido_em",
        "duracao_segundos",
        "criado_em",
        "atualizado_em",
    )
    inlines = (DiagnosticoPaginaEmLinha, ArtefatoProcessadoEmLinha)

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(DiagnosticoPagina)
class AdministracaoDiagnosticoPagina(admin.ModelAdmin):
    list_display = (
        "processamento",
        "numero_pagina",
        "rota",
        "tipo_pagina",
        "quantidade_caracteres",
        "quantidade_imagens",
    )
    list_filter = ("rota", "tipo_pagina", "tabela_suspeita", "mapa_suspeito")
    readonly_fields = (
        "processamento",
        "numero_pagina",
        "rota",
        "tipo_pagina",
        "possui_texto_nativo",
        "quantidade_caracteres",
        "quantidade_imagens",
        "tabela_suspeita",
        "mapa_suspeito",
        "modo_extracao",
        "texto_rotacionado",
        "avisos",
        "dados_tecnicos",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(ArtefatoProcessado)
class AdministracaoArtefatoProcessado(admin.ModelAdmin):
    list_display = ("processamento", "tipo", "mime_type", "tamanho_bytes", "criado_em")
    list_filter = ("tipo", "mime_type")
    search_fields = ("sha256", "processamento__versao_documento__nome_original")
    readonly_fields = (
        "processamento",
        "tipo",
        "arquivo",
        "sha256",
        "tamanho_bytes",
        "mime_type",
        "metadados",
        "criado_em",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


class ArtigoNormativoEmLinha(admin.TabularInline):
    model = ArtigoNormativo
    extra = 0
    fields = (
        "rotulo",
        "pagina_inicial",
        "pagina_final",
        "status_sequencia",
        "status_auditoria",
        "fonte_pos_bloco",
    )
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None) -> bool:
        return False


class AnexoNormativoEmLinha(admin.TabularInline):
    model = AnexoNormativo
    extra = 0
    fields = ("titulo", "tipo", "pagina_inicial", "pagina_final", "status")
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(AtoNormativo)
class AdministracaoAtoNormativo(admin.ModelAdmin):
    list_display = (
        "identificador",
        "versao_documento",
        "natureza_texto",
        "pagina_inicial",
        "pagina_final",
        "status_auditoria",
    )
    list_filter = ("natureza_texto", "status_auditoria", "ano")
    search_fields = (
        "identificador",
        "especie",
        "numero",
        "ementa",
        "versao_documento__documento__titulo",
    )
    autocomplete_fields = ("versao_documento",)
    inlines = (ArtigoNormativoEmLinha, AnexoNormativoEmLinha)


@admin.register(ArtigoNormativo)
class AdministracaoArtigoNormativo(admin.ModelAdmin):
    list_display = (
        "identificador",
        "ato",
        "rotulo",
        "pagina_inicial",
        "pagina_final",
        "status_sequencia",
        "status_auditoria",
        "fonte_pos_bloco",
    )
    list_filter = (
        "status_sequencia",
        "status_auditoria",
        "heading_encontrado",
        "fonte_pos_bloco",
    )
    search_fields = ("identificador", "rotulo", "numero_textual", "texto", "ato__identificador")
    autocomplete_fields = ("ato",)
    readonly_fields = ("sha256_texto", "criado_em", "atualizado_em")


@admin.register(AnexoNormativo)
class AdministracaoAnexoNormativo(admin.ModelAdmin):
    list_display = ("identificador", "ato", "titulo", "tipo", "status", "pagina_inicial")
    list_filter = ("tipo", "status")
    search_fields = ("identificador", "titulo", "ato__identificador")
    autocomplete_fields = ("ato", "artigo_referencia")


class AdjudicacaoDocumentalEmLinha(admin.StackedInline):
    model = AdjudicacaoDocumental
    extra = 0
    max_num = 1
    show_change_link = True


@admin.register(OcorrenciaDocumental)
class AdministracaoOcorrenciaDocumental(admin.ModelAdmin):
    list_display = (
        "id",
        "categoria",
        "severidade",
        "estado",
        "versao_documento",
        "pagina",
        "bloqueia_release",
    )
    list_filter = ("severidade", "estado", "categoria")
    search_fields = (
        "descricao",
        "decisao",
        "versao_documento__documento__titulo",
        "ato__identificador",
        "artigo__identificador",
    )
    autocomplete_fields = ("versao_documento", "ato", "artigo", "anexo", "resolvida_por")
    inlines = (AdjudicacaoDocumentalEmLinha,)

    @admin.display(boolean=True, description="Bloqueia release")
    def bloqueia_release(self, ocorrencia: OcorrenciaDocumental) -> bool:
        return ocorrencia.bloqueia_release


@admin.register(AdjudicacaoDocumental)
class AdministracaoAdjudicacaoDocumental(admin.ModelAdmin):
    list_display = ("ocorrencia", "estado_resultante", "responsavel", "criado_em")
    list_filter = ("estado_resultante",)
    search_fields = ("decisao", "fundamento", "ocorrencia__descricao")
    autocomplete_fields = ("ocorrencia", "responsavel")


class ReleaseCorpusDocumentoEmLinha(admin.TabularInline):
    model = ReleaseCorpusDocumento
    extra = 0
    autocomplete_fields = ("versao_documento",)


@admin.register(ReleaseCorpus)
class AdministracaoReleaseCorpus(admin.ModelAdmin):
    list_display = (
        "aplicacao",
        "versao",
        "estado",
        "status_indexacao",
        "status_validacao",
        "liberado_em",
    )
    list_filter = ("estado", "status_indexacao", "status_validacao")
    search_fields = ("aplicacao__titulo", "aplicacao__municipio__nome", "versao", "manifesto_sha256")
    autocomplete_fields = ("aplicacao", "liberado_por")
    readonly_fields = ("criado_em", "atualizado_em")
    inlines = (ReleaseCorpusDocumentoEmLinha,)


@admin.register(LeituraIntegral)
class AdministracaoLeituraIntegral(admin.ModelAdmin):
    list_display = (
        "aplicacao",
        "artigo",
        "release_corpus",
        "revisado",
        "confianca",
        "revisado_em",
        "atualizado_em",
    )
    list_filter = ("revisado", "release_corpus__estado", "lido_por_modelo")
    search_fields = (
        "aplicacao__titulo",
        "aplicacao__municipio__nome",
        "artigo__identificador",
        "artigo__rotulo",
        "release_corpus__versao",
        "resumo",
    )
    autocomplete_fields = ("aplicacao", "artigo", "release_corpus", "revisado_por")
    readonly_fields = ("criado_em", "atualizado_em", "revisado_em")


@admin.register(LivroCobertura)
class AdministracaoLivroCobertura(admin.ModelAdmin):
    list_display = (
        "release_corpus",
        "total_artigos",
        "total_lidos",
        "total_revisados",
        "cobertura_percentual",
        "gerado_em",
        "atualizado_em",
    )
    list_filter = ("release_corpus__estado", "gerado_em")
    search_fields = (
        "release_corpus__aplicacao__titulo",
        "release_corpus__aplicacao__municipio__nome",
        "release_corpus__versao",
        "sha256_estado",
    )
    autocomplete_fields = ("release_corpus",)
    readonly_fields = ("gerado_em", "criado_em", "atualizado_em")


@admin.register(ContextoNormativoC0)
class AdministracaoContextoNormativoC0(admin.ModelAdmin):
    list_display = (
        "aplicacao",
        "release_corpus",
        "cobertura_integral",
        "revisado",
        "revisado_em",
        "atualizado_em",
    )
    list_filter = ("cobertura_integral", "revisado", "release_corpus__estado")
    search_fields = (
        "aplicacao__titulo",
        "aplicacao__municipio__nome",
        "release_corpus__versao",
        "observacoes",
    )
    autocomplete_fields = ("aplicacao", "release_corpus", "revisado_por")
    readonly_fields = ("criado_em", "atualizado_em", "revisado_em")
