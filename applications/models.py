from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


def caminho_arquivo_documento(instance: VersaoDocumento, nome_arquivo: str) -> str:
    """Gera um caminho estável para o arquivo original com base em seu hash."""
    extensao = Path(nome_arquivo).suffix.lower()
    identificador = instance.sha256 or "hash-pendente"
    return f"immutable/documentos/{instance.documento_id}/{identificador}{extensao}"


def caminho_artefato_processado(instance: ArtefatoProcessado, nome_arquivo: str) -> str:
    """Gera caminho estável para artefatos derivados de um processamento."""
    extensao = Path(nome_arquivo).suffix.lower() or ".bin"
    identificador = instance.sha256 or "hash-pendente"
    return f"derived/processamentos/{instance.processamento_id}/{identificador}{extensao}"


class RegistroTemporal(models.Model):
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Municipio(RegistroTemporal):
    nome = models.CharField(max_length=150)
    uf = models.CharField("UF", max_length=2)
    codigo_ibge = models.CharField("código IBGE", max_length=7, blank=True, null=True, unique=True)
    codigo_uf = models.CharField("código da UF", max_length=2, blank=True)
    nome_uf = models.CharField("nome da UF", max_length=50, blank=True)
    ativo = models.BooleanField(default=True)
    fonte_dados = models.URLField(blank=True)
    data_referencia = models.DateField(blank=True, null=True)
    sha256_fonte = models.CharField(max_length=64, blank=True, editable=False)
    geometria_geojson = models.JSONField(
        "geometria GeoJSON",
        blank=True,
        null=True,
        editable=False,
    )
    fonte_geometria = models.URLField(blank=True, editable=False)
    data_referencia_geometria = models.DateField(blank=True, null=True, editable=False)
    sha256_geometria = models.CharField(max_length=64, blank=True, editable=False)
    geometria_atualizada_em = models.DateTimeField(blank=True, null=True, editable=False)

    class Meta:
        ordering = ["uf", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["nome", "uf"], name="municipio_nome_uf_unicos")
        ]
        verbose_name = "município"
        verbose_name_plural = "municípios"

    def __str__(self) -> str:
        identificador = f" — IBGE {self.codigo_ibge}" if self.codigo_ibge else ""
        return f"{self.nome}/{self.uf.upper()}{identificador}"

    def save(self, *args, **kwargs) -> None:
        self.uf = self.uf.strip().upper()
        super().save(*args, **kwargs)


class AplicacaoMunicipal(RegistroTemporal):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        CORPUS_RECEBIDO = "corpus_recebido", "Corpus recebido"
        CORPUS_LIBERADO = "corpus_liberado", "Corpus liberado"
        EM_ANALISE = "em_analise", "Em análise"
        EM_VALIDACAO = "em_validacao", "Em validação"
        CONCLUIDA = "concluida", "Concluída"

    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.PROTECT,
        related_name="aplicacoes",
    )
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RASCUNHO)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "aplicação municipal"
        verbose_name_plural = "aplicações municipais"

    def __str__(self) -> str:
        return f"{self.municipio} — {self.titulo}"


class TipoNormativo(RegistroTemporal):
    class Esfera(models.TextChoices):
        GERAL = "geral", "Geral"
        FEDERAL = "federal", "Federal"
        ESTADUAL = "estadual", "Estadual"
        MUNICIPAL = "municipal", "Municipal"

    codigo = models.SlugField(max_length=60, unique=True)
    nome = models.CharField(max_length=150)
    sigla = models.CharField(max_length=20, blank=True)
    esfera = models.CharField(max_length=12, choices=Esfera.choices, default=Esfera.GERAL)
    fonte_normativa = models.URLField()
    dispositivo_fonte = models.CharField(max_length=255)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    ordem_exibicao = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordem_exibicao", "nome"]
        verbose_name = "tipo normativo"
        verbose_name_plural = "tipos normativos"

    def __str__(self) -> str:
        return self.nome


class DocumentoNormativo(RegistroTemporal):
    class Status(models.TextChoices):
        RECEBIDO = "recebido", "Recebido"
        VERIFICADO = "verificado", "Verificado"
        QUARENTENA = "quarentena", "Em quarentena"
        LIBERADO = "liberado", "Liberado para análise"

    aplicacao = models.ForeignKey(
        AplicacaoMunicipal,
        on_delete=models.CASCADE,
        related_name="documentos",
    )
    tipo = models.ForeignKey(
        TipoNormativo,
        on_delete=models.PROTECT,
        related_name="documentos",
    )
    numero = models.CharField(max_length=40)
    ano = models.PositiveSmallIntegerField()
    titulo = models.CharField(max_length=255)
    data_publicacao = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEBIDO)

    class Meta:
        ordering = ["ano", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["aplicacao", "tipo", "numero", "ano"],
                name="documento_identidade_unica_aplicacao",
            )
        ]
        verbose_name = "documento normativo"
        verbose_name_plural = "documentos normativos"

    def __str__(self) -> str:
        return f"{self.tipo.nome} nº {self.numero}/{self.ano}"


class VersaoDocumento(models.Model):
    class SituacaoIngestao(models.TextChoices):
        ORIGINAL = "original", "Original"
        DUPLICADO = "duplicado", "Duplicado"

    documento = models.ForeignKey(
        DocumentoNormativo,
        on_delete=models.CASCADE,
        related_name="versoes",
    )
    versao = models.PositiveSmallIntegerField(default=1)
    arquivo = models.FileField(upload_to=caminho_arquivo_documento)
    nome_original = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=120, blank=True)
    sha256 = models.CharField(max_length=64, editable=False, db_index=True)
    tamanho_bytes = models.PositiveBigIntegerField(editable=False, default=0)
    origem_recebimento = models.CharField(max_length=255, blank=True)
    observacoes_ingestao = models.TextField(blank=True)
    situacao_ingestao = models.CharField(
        max_length=16,
        choices=SituacaoIngestao.choices,
        default=SituacaoIngestao.ORIGINAL,
        editable=False,
    )
    duplicado_de = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="duplicatas",
        blank=True,
        null=True,
        editable=False,
    )
    original_preservado = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["documento", "versao"]
        constraints = [
            models.UniqueConstraint(
                fields=["documento", "versao"],
                name="versao_unica_por_documento",
            )
        ]
        verbose_name = "versão documental"
        verbose_name_plural = "versões documentais"

    def __str__(self) -> str:
        return f"{self.documento} — versão {self.versao}"

    def _calcular_sha256(self) -> str:
    resumo = sha256()
    estava_fechado = self.arquivo.closed
    arquivo = self.arquivo.file

    try:
        posicao_original = arquivo.tell() if arquivo.seekable() else None
        arquivo.seek(0)

        if hasattr(arquivo, "chunks"):
            for bloco in arquivo.chunks():
                resumo.update(bloco)
        else:
            while bloco := arquivo.read(1024 * 1024):
                resumo.update(bloco)

        if posicao_original is not None:
            arquivo.seek(posicao_original)

        return resumo.hexdigest()
    finally:
        if estava_fechado:
            self.arquivo.close()
    def _localizar_duplicado(self) -> VersaoDocumento | None:
        consulta = VersaoDocumento.objects.filter(
            documento__aplicacao=self.documento.aplicacao,
            sha256=self.sha256,
        )
        if self.pk:
            consulta = consulta.exclude(pk=self.pk)
        return consulta.order_by("criado_em", "pk").first()

    def save(self, *args, **kwargs) -> None:
        if self.arquivo and not self.sha256:
            self.tamanho_bytes = self.arquivo.size
            if self.tamanho_bytes == 0:
                raise ValidationError({"arquivo": "O arquivo recebido está vazio."})
            if not self.nome_original:
                self.nome_original = Path(self.arquivo.name).name
            self.sha256 = self._calcular_sha256()
            duplicado = self._localizar_duplicado()
            if duplicado:
                self.duplicado_de = duplicado
                self.situacao_ingestao = self.SituacaoIngestao.DUPLICADO
            else:
                self.duplicado_de = None
                self.situacao_ingestao = self.SituacaoIngestao.ORIGINAL
        super().save(*args, **kwargs)


class ProcessamentoDocumento(RegistroTemporal):
    class Etapa(models.TextChoices):
        QUALIFICACAO = "qualificacao", "Qualificação documental"
        CONVERSAO = "conversao", "Conversão"
        VALIDACAO = "validacao", "Validação"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        EM_EXECUCAO = "em_execucao", "Em execução"
        CONCLUIDO = "concluido", "Concluído"
        FALHOU = "falhou", "Falhou"

    class RotaDocumento(models.TextChoices):
        TEXTO_NATIVO = "texto_nativo", "Texto nativo"
        OCR = "ocr", "OCR"
        MISTO = "misto", "Misto"
        VISUAL_COMPLEXO = "visual_complexo", "Visual complexo"
        MANUAL = "manual", "Revisão manual"

    versao_documento = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.CASCADE,
        related_name="processamentos",
    )
    etapa = models.CharField(max_length=20, choices=Etapa.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    rota_documento = models.CharField(
        max_length=24,
        choices=RotaDocumento.choices,
        blank=True,
    )
    ferramenta = models.CharField(max_length=120)
    versao_ferramenta = models.CharField(max_length=80, blank=True)
    versao_codigo = models.CharField(max_length=64, blank=True)
    parametros = models.JSONField(default=dict, blank=True)
    metricas = models.JSONField(default=dict, blank=True)
    avisos = models.JSONField(default=list, blank=True)
    mensagem_erro = models.TextField(blank=True)
    iniciado_em = models.DateTimeField(blank=True, null=True)
    concluido_em = models.DateTimeField(blank=True, null=True)
    duracao_segundos = models.FloatField(blank=True, null=True)

    class Meta:
        ordering = ["-criado_em", "-pk"]
        verbose_name = "processamento documental"
        verbose_name_plural = "processamentos documentais"

    def __str__(self) -> str:
        return f"{self.versao_documento} — {self.get_etapa_display()} — {self.get_status_display()}"


class DiagnosticoPagina(models.Model):
    processamento = models.ForeignKey(
        ProcessamentoDocumento,
        on_delete=models.CASCADE,
        related_name="diagnosticos_paginas",
    )
    numero_pagina = models.PositiveIntegerField()
    rota = models.CharField(max_length=24)
    tipo_pagina = models.CharField(max_length=40)
    possui_texto_nativo = models.BooleanField(default=False)
    quantidade_caracteres = models.PositiveIntegerField(default=0)
    quantidade_imagens = models.PositiveIntegerField(default=0)
    tabela_suspeita = models.BooleanField(default=False)
    mapa_suspeito = models.BooleanField(default=False)
    modo_extracao = models.CharField(max_length=40, blank=True)
    texto_rotacionado = models.BooleanField(default=False)
    avisos = models.JSONField(default=list, blank=True)
    dados_tecnicos = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["processamento", "numero_pagina"]
        constraints = [
            models.UniqueConstraint(
                fields=["processamento", "numero_pagina"],
                name="diagnostico_pagina_unico_processamento",
            )
        ]
        verbose_name = "diagnóstico de página"
        verbose_name_plural = "diagnósticos de páginas"

    def __str__(self) -> str:
        return f"{self.processamento} — página {self.numero_pagina}"


class ArtefatoProcessado(models.Model):
    class Tipo(models.TextChoices):
        DIAGNOSTICO_JSON = "diagnostico_json", "Diagnóstico JSON"
        MARKDOWN = "markdown", "Markdown"
        LOG = "log", "Log"
        OUTRO = "outro", "Outro"

    processamento = models.ForeignKey(
        ProcessamentoDocumento,
        on_delete=models.CASCADE,
        related_name="artefatos",
    )
    tipo = models.CharField(max_length=24, choices=Tipo.choices)
    arquivo = models.FileField(upload_to=caminho_artefato_processado)
    sha256 = models.CharField(max_length=64, editable=False, db_index=True)
    tamanho_bytes = models.PositiveBigIntegerField(editable=False)
    mime_type = models.CharField(max_length=120)
    metadados = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["processamento", "tipo"]
        constraints = [
            models.UniqueConstraint(
                fields=["processamento", "tipo"],
                name="artefato_tipo_unico_processamento",
            )
        ]
        verbose_name = "artefato processado"
        verbose_name_plural = "artefatos processados"

    def __str__(self) -> str:
        return f"{self.processamento} — {self.get_tipo_display()}"


class AtoNormativo(RegistroTemporal):
    class NaturezaTexto(models.TextChoices):
        ORIGINAL = "original", "Original"
        MODIFICADOR = "modificador", "Ato modificador"
        CONSOLIDADO_OFICIAL = "consolidado_oficial", "Consolidado oficial"
        COMPILACAO = "compilacao", "Compilação"
        NAO_IDENTIFICADA = "nao_identificada", "Não identificada"

    class StatusAuditoria(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        EM_REVISAO = "em_revisao", "Em revisão"
        APROVADO = "aprovado", "Aprovado"
        REPROVADO = "reprovado", "Reprovado"

    versao_documento = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.CASCADE,
        related_name="atos_normativos",
    )
    identificador = models.SlugField(max_length=180, unique=True)
    especie = models.CharField(max_length=120, blank=True)
    numero = models.CharField(max_length=40, blank=True)
    ano = models.PositiveSmallIntegerField(blank=True, null=True)
    data_norma = models.DateField(blank=True, null=True)
    ementa = models.TextField(blank=True)
    natureza_texto = models.CharField(
        max_length=24,
        choices=NaturezaTexto.choices,
        default=NaturezaTexto.NAO_IDENTIFICADA,
    )
    pagina_inicial = models.PositiveIntegerField()
    pagina_final = models.PositiveIntegerField()
    primeiro_artigo = models.CharField(max_length=40, blank=True)
    ultimo_artigo = models.CharField(max_length=40, blank=True)
    status_auditoria = models.CharField(
        max_length=16,
        choices=StatusAuditoria.choices,
        default=StatusAuditoria.PENDENTE,
    )
    metadados = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["versao_documento", "pagina_inicial", "identificador"]
        constraints = [
            models.CheckConstraint(
                condition=Q(pagina_final__gte=models.F("pagina_inicial")),
                name="ato_pagina_final_maior_igual_inicial",
            ),
            models.UniqueConstraint(
                fields=["versao_documento", "pagina_inicial", "pagina_final"],
                name="ato_intervalo_unico_por_versao",
            ),
        ]
        verbose_name = "ato normativo"
        verbose_name_plural = "atos normativos"

    def __str__(self) -> str:
        referencia = " ".join(parte for parte in [self.especie, self.numero, str(self.ano or "")] if parte)
        return referencia or self.identificador


class ArtigoNormativo(RegistroTemporal):
    class StatusSequencia(models.TextChoices):
        REGULAR = "regular", "Regular"
        LACUNA = "lacuna", "Lacuna"
        DUPLICADO = "duplicado", "Duplicado"
        IRREGULAR_ORIGINAL = "irregular_original", "Irregularidade original"
        NAO_RESOLVIDO = "nao_resolvido", "Não resolvido"

    class StatusAuditoria(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        AUTOMATICA = "automatica", "Auditoria automática"
        REVISADO = "revisado", "Revisado"
        ADJUDICADO = "adjudicado", "Adjudicado"

    ato = models.ForeignKey(
        AtoNormativo,
        on_delete=models.CASCADE,
        related_name="artigos",
    )
    identificador = models.SlugField(max_length=220, unique=True)
    rotulo = models.CharField(max_length=80)
    numero_textual = models.CharField(max_length=40)
    numero_normalizado = models.PositiveIntegerField(blank=True, null=True)
    sufixo = models.CharField(max_length=12, blank=True)
    pagina_inicial = models.PositiveIntegerField()
    pagina_final = models.PositiveIntegerField()
    heading_encontrado = models.BooleanField(default=True)
    fonte_pos_bloco = models.BooleanField(default=False)
    texto = models.TextField()
    estrutura = models.JSONField(default=dict, blank=True)
    sha256_texto = models.CharField(max_length=64, blank=True, editable=False, db_index=True)
    status_sequencia = models.CharField(
        max_length=24,
        choices=StatusSequencia.choices,
        default=StatusSequencia.REGULAR,
    )
    status_auditoria = models.CharField(
        max_length=16,
        choices=StatusAuditoria.choices,
        default=StatusAuditoria.PENDENTE,
    )
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ["ato", "pagina_inicial", "numero_normalizado", "sufixo", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(pagina_final__gte=models.F("pagina_inicial")),
                name="artigo_pagina_final_maior_igual_inicial",
            ),
            models.UniqueConstraint(
                fields=["ato", "numero_textual", "sufixo"],
                name="artigo_numero_sufixo_unico_por_ato",
            ),
        ]
        verbose_name = "artigo normativo"
        verbose_name_plural = "artigos normativos"

    def __str__(self) -> str:
        return f"{self.ato} — {self.rotulo}"

    def save(self, *args, **kwargs) -> None:
        if self.texto:
            self.sha256_texto = sha256(self.texto.encode("utf-8")).hexdigest()
        super().save(*args, **kwargs)


class AnexoNormativo(RegistroTemporal):
    class Tipo(models.TextChoices):
        TEXTO = "texto", "Texto"
        TABELA = "tabela", "Tabela"
        MAPA = "mapa", "Mapa"
        COORDENADAS = "coordenadas", "Coordenadas"
        FORMULARIO = "formulario", "Formulário"
        OUTRO = "outro", "Outro"

    class Status(models.TextChoices):
        IDENTIFICADO = "identificado", "Identificado"
        EXTRAIDO = "extraido", "Extraído"
        REVISADO = "revisado", "Revisado"
        PENDENTE = "pendente", "Pendente"

    ato = models.ForeignKey(
        AtoNormativo,
        on_delete=models.CASCADE,
        related_name="anexos",
    )
    artigo_referencia = models.ForeignKey(
        ArtigoNormativo,
        on_delete=models.SET_NULL,
        related_name="anexos_referenciados",
        blank=True,
        null=True,
    )
    identificador = models.SlugField(max_length=220, unique=True)
    titulo = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    pagina_inicial = models.PositiveIntegerField(blank=True, null=True)
    pagina_final = models.PositiveIntegerField(blank=True, null=True)
    destino = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IDENTIFICADO)
    metadados = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["ato", "pagina_inicial", "titulo"]
        constraints = [
            models.CheckConstraint(
                condition=Q(pagina_final__isnull=True)
                | Q(pagina_inicial__isnull=True)
                | Q(pagina_final__gte=models.F("pagina_inicial")),
                name="anexo_pagina_final_maior_igual_inicial",
            )
        ]
        verbose_name = "anexo normativo"
        verbose_name_plural = "anexos normativos"

    def __str__(self) -> str:
        return f"{self.ato} — {self.titulo}"


class OcorrenciaDocumental(RegistroTemporal):
    class Severidade(models.TextChoices):
        CRITICA = "critica", "Crítica"
        ALTA = "alta", "Alta"
        MEDIA = "media", "Média"
        BAIXA = "baixa", "Baixa"

    class Estado(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        EM_ANALISE = "em_analise", "Em análise"
        RESOLVIDA = "resolvida", "Resolvida"
        ACEITA = "aceita", "Aceita como irregularidade da fonte"
        NAO_RESOLVIDA = "nao_resolvida", "Não resolvida"

    versao_documento = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.CASCADE,
        related_name="ocorrencias_documentais",
    )
    ato = models.ForeignKey(
        AtoNormativo,
        on_delete=models.CASCADE,
        related_name="ocorrencias",
        blank=True,
        null=True,
    )
    artigo = models.ForeignKey(
        ArtigoNormativo,
        on_delete=models.CASCADE,
        related_name="ocorrencias",
        blank=True,
        null=True,
    )
    anexo = models.ForeignKey(
        AnexoNormativo,
        on_delete=models.CASCADE,
        related_name="ocorrencias",
        blank=True,
        null=True,
    )
    categoria = models.CharField(max_length=80)
    severidade = models.CharField(max_length=12, choices=Severidade.choices)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABERTA)
    pagina = models.PositiveIntegerField(blank=True, null=True)
    descricao = models.TextField()
    evidencias = models.JSONField(default=list, blank=True)
    decisao = models.TextField(blank=True)
    resolvida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="ocorrencias_documentais_resolvidas",
        blank=True,
        null=True,
    )
    resolvida_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-severidade", "estado", "versao_documento", "pagina", "pk"]
        verbose_name = "ocorrência documental"
        verbose_name_plural = "ocorrências documentais"

    def __str__(self) -> str:
        return f"{self.get_severidade_display()} — {self.categoria} — {self.get_estado_display()}"

    @property
    def bloqueia_release(self) -> bool:
        return self.severidade == self.Severidade.CRITICA and self.estado not in {
            self.Estado.RESOLVIDA,
            self.Estado.ACEITA,
        }


class AdjudicacaoDocumental(RegistroTemporal):
    ocorrencia = models.OneToOneField(
        OcorrenciaDocumental,
        on_delete=models.CASCADE,
        related_name="adjudicacao",
    )
    decisao = models.TextField()
    fundamento = models.TextField()
    impacto = models.TextField(blank=True)
    estado_resultante = models.CharField(max_length=20, choices=OcorrenciaDocumental.Estado.choices)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="adjudicacoes_documentais",
    )

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "adjudicação documental"
        verbose_name_plural = "adjudicações documentais"

    def __str__(self) -> str:
        return f"Adjudicação da ocorrência {self.ocorrencia_id}"


class ReleaseCorpus(RegistroTemporal):
    class Estado(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        EM_VALIDACAO = "em_validacao", "Em validação"
        LIBERADO = "liberado", "Liberado"
        SUBSTITUIDO = "substituido", "Substituído"
        REVOGADO = "revogado", "Revogado"

    class StatusIndexacao(models.TextChoices):
        A = "A", "A — pronto para indexação"
        B = "B", "B — indexável com ressalvas"
        C = "C", "C — não indexar"

    class StatusValidacao(models.TextChoices):
        NAO_VALIDADO = "V0", "V0 — não validado"
        EXPLORACAO = "V1", "V1 — exploração"
        ANALISE_TECNICA = "V2", "V2 — análise técnica"
        BENCHMARK = "V3", "V3 — benchmark ou uso sensível"

    aplicacao = models.ForeignKey(
        AplicacaoMunicipal,
        on_delete=models.CASCADE,
        related_name="releases_corpus",
    )
    versao = models.CharField(max_length=30)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.RASCUNHO)
    status_indexacao = models.CharField(
        max_length=1,
        choices=StatusIndexacao.choices,
        default=StatusIndexacao.C,
    )
    status_validacao = models.CharField(
        max_length=2,
        choices=StatusValidacao.choices,
        default=StatusValidacao.NAO_VALIDADO,
    )
    protocolo_conversao = models.CharField(max_length=40, default="PCR-NORM-RAG v1.1")
    manifesto_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    metricas = models.JSONField(default=dict, blank=True)
    observacoes = models.TextField(blank=True)
    liberado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="releases_corpus_liberados",
        blank=True,
        null=True,
    )
    liberado_em = models.DateTimeField(blank=True, null=True)
    versoes_documentais = models.ManyToManyField(
        VersaoDocumento,
        through="ReleaseCorpusDocumento",
        related_name="releases_corpus",
    )

    class Meta:
        ordering = ["aplicacao", "-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["aplicacao", "versao"],
                name="release_versao_unica_por_aplicacao",
            )
        ]
        verbose_name = "release de corpus"
        verbose_name_plural = "releases de corpus"

    def __str__(self) -> str:
        return f"{self.aplicacao} — release {self.versao}"

    @property
    def pode_ser_liberado(self) -> bool:
        return not OcorrenciaDocumental.objects.filter(
            versao_documento__releasecorpusdocumento__release=self,
            severidade=OcorrenciaDocumental.Severidade.CRITICA,
        ).exclude(
            estado__in=[
                OcorrenciaDocumental.Estado.RESOLVIDA,
                OcorrenciaDocumental.Estado.ACEITA,
            ]
        ).exists()


class ReleaseCorpusDocumento(models.Model):
    release = models.ForeignKey(
        ReleaseCorpus,
        on_delete=models.CASCADE,
        related_name="documentos_release",
    )
    versao_documento = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.PROTECT,
        related_name="vinculos_release",
    )
    incluído_em = models.DateTimeField(auto_now_add=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ["release", "versao_documento"]
        constraints = [
            models.UniqueConstraint(
                fields=["release", "versao_documento"],
                name="release_documento_unico",
            )
        ]
        verbose_name = "documento de release"
        verbose_name_plural = "documentos de release"

    def __str__(self) -> str:
        return f"{self.release} — {self.versao_documento}"
