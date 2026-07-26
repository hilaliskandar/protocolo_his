from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from applications.models import VersaoDocumento


class ClassificacaoVersao(models.Model):
    class Natureza(models.TextChoices):
        TEXTO_ORIGINAL = "texto_original", "Texto original"
        CONSOLIDACAO_OFICIAL = "consolidacao_oficial", "Consolidação oficial"
        REPUBLICACAO = "republicacao", "Republicação"
        RETIFICACAO = "retificacao", "Retificação"
        COPIA = "copia", "Cópia"
        INDETERMINADA = "indeterminada", "Indeterminada"

    class Estado(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        CONFIRMADA = "confirmada", "Confirmada"
        REJEITADA = "rejeitada", "Rejeitada"

    versao_documento = models.OneToOneField(
        VersaoDocumento,
        on_delete=models.CASCADE,
        related_name="classificacao_normativa",
    )
    natureza = models.CharField(
        max_length=24,
        choices=Natureza.choices,
        default=Natureza.INDETERMINADA,
    )
    data_referencia_normativa = models.DateField(blank=True, null=True)
    referencia_atualizacao = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=16, choices=Estado.choices, default=Estado.PENDENTE)
    justificativa = models.TextField(blank=True)
    fonte = models.CharField(max_length=255, blank=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="classificacoes_versao_confirmadas",
        blank=True,
        null=True,
    )
    confirmado_em = models.DateTimeField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["versao_documento"]
        verbose_name = "classificação de versão normativa"
        verbose_name_plural = "classificações de versões normativas"

    def __str__(self) -> str:
        return f"{self.versao_documento} — {self.get_natureza_display()}"

    def clean(self) -> None:
        erros: dict[str, str] = {}
        if self.estado == self.Estado.CONFIRMADA:
            if not self.confirmado_por_id:
                erros["confirmado_por"] = "Uma classificação confirmada exige responsável."
            if not self.confirmado_em:
                erros["confirmado_em"] = "Uma classificação confirmada exige data e hora."
            if not self.justificativa.strip():
                erros["justificativa"] = "Uma classificação confirmada exige justificativa."
        elif self.confirmado_por_id or self.confirmado_em:
            erros["estado"] = "Responsável e data só podem ser registrados em classificação confirmada."
        if erros:
            raise ValidationError(erros)


class RelacaoVersoes(models.Model):
    class Tipo(models.TextChoices):
        SUCESSAO = "sucessao", "Sucessão"
        EQUIVALENCIA = "equivalencia", "Equivalência"
        DERIVACAO = "derivacao", "Derivação"

    class Estado(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        CONFIRMADA = "confirmada", "Confirmada"
        REJEITADA = "rejeitada", "Rejeitada"

    versao_origem = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.PROTECT,
        related_name="relacoes_como_origem",
    )
    versao_destino = models.ForeignKey(
        VersaoDocumento,
        on_delete=models.PROTECT,
        related_name="relacoes_como_destino",
    )
    tipo = models.CharField(max_length=16, choices=Tipo.choices)
    estado = models.CharField(max_length=16, choices=Estado.choices, default=Estado.PENDENTE)
    justificativa = models.TextField()
    fonte = models.CharField(max_length=255, blank=True)
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="relacoes_versoes_validadas",
        blank=True,
        null=True,
    )
    validado_em = models.DateTimeField(blank=True, null=True)
    metadados = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["versao_origem", "versao_destino", "tipo"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(versao_origem=F("versao_destino")),
                name="relacao_versoes_origem_destino_distintos",
            ),
            models.UniqueConstraint(
                fields=["versao_origem", "versao_destino", "tipo"],
                name="relacao_versoes_unica_por_tipo",
            ),
        ]
        verbose_name = "relação entre versões normativas"
        verbose_name_plural = "relações entre versões normativas"

    def __str__(self) -> str:
        return f"{self.versao_origem} → {self.versao_destino} ({self.get_tipo_display()})"

    def clean(self) -> None:
        erros: dict[str, str] = {}
        origem = self.versao_origem if self.versao_origem_id else None
        destino = self.versao_destino if self.versao_destino_id else None

        if origem and destino:
            if origem.pk == destino.pk:
                erros["versao_destino"] = "Origem e destino devem ser versões distintas."
            if origem.documento.aplicacao_id != destino.documento.aplicacao_id:
                erros["versao_destino"] = "As versões devem pertencer à mesma aplicação municipal."
            if self.tipo == self.Tipo.SUCESSAO:
                if origem.documento_id != destino.documento_id:
                    erros["versao_destino"] = "Sucessão exige versões do mesmo documento normativo."
                elif origem.versao >= destino.versao:
                    erros["versao_destino"] = "Na sucessão, o destino deve ser posterior à origem."

        if not self.justificativa.strip():
            erros["justificativa"] = "A relação exige justificativa."

        if self.estado == self.Estado.CONFIRMADA:
            if not self.validado_por_id:
                erros["validado_por"] = "Uma relação confirmada exige responsável."
            if not self.validado_em:
                erros["validado_em"] = "Uma relação confirmada exige data e hora."
        elif self.validado_por_id or self.validado_em:
            erros["estado"] = "Responsável e data só podem ser registrados em relação confirmada."

        if erros:
            raise ValidationError(erros)
