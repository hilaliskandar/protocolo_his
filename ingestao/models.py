from __future__ import annotations

import uuid
from hashlib import sha256
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models


def caminho_lote(instance: ImportacaoLote, nome_arquivo: str) -> str:
    extensao = Path(nome_arquivo).suffix.lower() or ".zip"
    return f"immutable/importacoes/{instance.pk}/lote{extensao}"


class ImportacaoLote(models.Model):
    class Status(models.TextChoices):
        RECEBIDO = "recebido", "Recebido"
        INSPECIONANDO = "inspecionando", "Inspecionando"
        INSPECIONADO = "inspecionado", "Inspecionado"
        CONFIRMANDO = "confirmando", "Confirmando"
        CONFIRMADO = "confirmado", "Confirmado"
        FALHOU = "falhou", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    origem_recebimento = models.CharField(max_length=255)
    uf_padrao = models.CharField(max_length=2, default="SP")
    arquivo_zip = models.FileField(upload_to=caminho_lote)
    nome_original = models.CharField(max_length=255, blank=True)
    sha256 = models.CharField(max_length=64, editable=False, db_index=True)
    tamanho_bytes = models.PositiveBigIntegerField(default=0, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEBIDO)
    parametros = models.JSONField(default=dict, blank=True)
    metricas = models.JSONField(default=dict, blank=True)
    avisos = models.JSONField(default=list, blank=True)
    mensagem_erro = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    iniciado_em = models.DateTimeField(blank=True, null=True)
    concluido_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "importação em lote"
        verbose_name_plural = "importações em lote"

    def save(self, *args, **kwargs) -> None:
        self.uf_padrao = self.uf_padrao.strip().upper()
        if self.arquivo_zip and not self.sha256:
            arquivo = self.arquivo_zip.file
            self.tamanho_bytes = self.arquivo_zip.size
            if self.tamanho_bytes == 0:
                raise ValidationError({"arquivo_zip": "O arquivo ZIP recebido está vazio."})
            if not self.nome_original:
                self.nome_original = Path(self.arquivo_zip.name).name
            resumo = sha256()
            posicao = arquivo.tell() if arquivo.seekable() else None
            arquivo.seek(0)
            while bloco := arquivo.read(1024 * 1024):
                resumo.update(bloco)
            if posicao is not None:
                arquivo.seek(posicao)
            self.sha256 = resumo.hexdigest()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.titulo} — {self.get_status_display()}"


class ItemImportacaoLote(models.Model):
    class Natureza(models.TextChoices):
        NORMATIVO_MUNICIPAL = "normativo_municipal", "Normativo municipal"
        NORMATIVO_ESTADUAL = "normativo_estadual", "Normativo estadual"
        NORMATIVO_FEDERAL = "normativo_federal", "Normativo federal"
        PLANO_HABITACIONAL = "plano_habitacional", "Plano habitacional"
        ESTUDO_TECNICO = "estudo_tecnico", "Estudo técnico"
        PAGINA_INSTITUCIONAL = "pagina_institucional", "Página institucional"
        DIARIO_OFICIAL = "diario_oficial", "Diário oficial"
        ANEXO_NORMATIVO = "anexo_normativo", "Anexo normativo"
        FRAGMENTO_NORMATIVO = "fragmento_normativo", "Fragmento normativo"
        OUTRO = "outro", "Outro documento de apoio"

    class Estado(models.TextChoices):
        PRONTO = "pronto", "Pronto para confirmar"
        REVISAO = "revisao", "Revisão humana"
        DUPLICADO = "duplicado", "Duplicado no lote"
        IGNORADO = "ignorado", "Ignorado"
        CONFIRMADO = "confirmado", "Confirmado"
        FALHOU = "falhou", "Falhou"

    lote = models.ForeignKey(ImportacaoLote, on_delete=models.CASCADE, related_name="itens")
    caminho_relativo = models.TextField()
    nome_original = models.CharField(max_length=255)
    municipio_candidato = models.CharField(max_length=150, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    natureza = models.CharField(max_length=32, choices=Natureza.choices, default=Natureza.OUTRO)
    tipo_normativo_codigo = models.CharField(max_length=60, blank=True)
    numero_candidato = models.CharField(max_length=40, blank=True)
    ano_candidato = models.PositiveSmallIntegerField(blank=True, null=True)
    titulo_candidato = models.CharField(max_length=255, blank=True)
    data_publicacao_candidata = models.DateField(blank=True, null=True)
    sha256 = models.CharField(max_length=64, db_index=True)
    tamanho_bytes = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(max_length=120, default="application/pdf")
    confianca = models.FloatField(default=0.0)
    avisos = models.JSONField(default=list, blank=True)
    estado = models.CharField(max_length=16, choices=Estado.choices, default=Estado.REVISAO)
    duplicado_de = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="duplicatas",
        blank=True,
        null=True,
    )
    documento_criado = models.ForeignKey(
        "applications.DocumentoNormativo",
        on_delete=models.SET_NULL,
        related_name="itens_importacao",
        blank=True,
        null=True,
    )
    versao_criada = models.ForeignKey(
        "applications.VersaoDocumento",
        on_delete=models.SET_NULL,
        related_name="itens_importacao",
        blank=True,
        null=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["caminho_relativo"]
        constraints = [
            models.UniqueConstraint(
                fields=["lote", "caminho_relativo"],
                name="item_importacao_caminho_unico",
            )
        ]
        verbose_name = "item de importação"
        verbose_name_plural = "itens de importação"

    def __str__(self) -> str:
        return self.caminho_relativo
