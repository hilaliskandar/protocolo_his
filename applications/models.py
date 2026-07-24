from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models


def caminho_arquivo_documento(instance: VersaoDocumento, nome_arquivo: str) -> str:
    """Gera um caminho estável para o arquivo original com base em seu hash."""
    extensao = Path(nome_arquivo).suffix.lower()
    identificador = instance.sha256 or "hash-pendente"
    return f"immutable/documentos/{instance.documento_id}/{identificador}{extensao}"


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
        arquivo = self.arquivo.file
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
