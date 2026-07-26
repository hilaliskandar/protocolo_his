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
    chave_idempotencia_sha256 = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        editable=False,
    )
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

    def _registro_existente(self) -> ImportacaoLote | None:
        if not self.pk:
            return None
        return type(self).objects.filter(pk=self.pk).only("arquivo_zip", "sha256").first()

    def clean(self) -> None:
        super().clean()
        self.uf_padrao = self.uf_padrao.strip().upper()
        if len(self.uf_padrao) != 2:
            raise ValidationError({"uf_padrao": "Informe uma UF com duas letras."})
        existente = self._registro_existente()
        if existente and (
            not self.arquivo_zip
            or not self.arquivo_zip._committed
            or existente.arquivo_zip.name != self.arquivo_zip.name
        ):
            raise ValidationError({"arquivo_zip": "O ZIP original é imutável após o recebimento."})
        if existente and self.sha256 != existente.sha256:
            raise ValidationError({"sha256": "O hash do ZIP original não pode ser alterado."})

    def save(self, *args, **kwargs) -> None:
        self.uf_padrao = self.uf_padrao.strip().upper()
        existente = self._registro_existente()
        if existente and (
            not self.arquivo_zip
            or not self.arquivo_zip._committed
            or existente.arquivo_zip.name != self.arquivo_zip.name
        ):
            raise ValidationError({"arquivo_zip": "O ZIP original é imutável após o recebimento."})
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

    class RotaSugerida(models.TextChoices):
        TEXTO_NATIVO = "texto_nativo", "Texto nativo"
        OCR = "ocr", "OCR"
        MISTO = "misto", "Misto"
        MANUAL = "manual", "Revisão manual"

    lote = models.ForeignKey(ImportacaoLote, on_delete=models.CASCADE, related_name="itens")
    indice_arquivo = models.PositiveIntegerField()
    caminho_relativo = models.TextField()
    nome_original = models.CharField(max_length=255)
    municipio_candidato = models.CharField(max_length=150, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    natureza = models.CharField(max_length=32, choices=Natureza.choices, default=Natureza.OUTRO)
    tipo_normativo_codigo = models.CharField(max_length=60, blank=True)
    numero_candidato = models.CharField(max_length=40, blank=True)
    numero_normalizado = models.CharField(max_length=40, blank=True, db_index=True)
    ano_candidato = models.PositiveSmallIntegerField(blank=True, null=True)
    titulo_candidato = models.CharField(max_length=255, blank=True)
    data_publicacao_candidata = models.DateField(blank=True, null=True)

    numero_sugerido_texto = models.CharField(max_length=40, blank=True, editable=False)
    numero_sugerido_normalizado = models.CharField(
        max_length=40, blank=True, db_index=True, editable=False
    )
    ano_sugerido_texto = models.PositiveSmallIntegerField(blank=True, null=True, editable=False)
    fontes_sugestoes = models.JSONField(default=dict, blank=True, editable=False)
    divergencias_metadados = models.JSONField(default=list, blank=True, editable=False)

    sha256 = models.CharField(max_length=64, db_index=True)
    tamanho_bytes = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(max_length=120, default="application/pdf")
    assinatura_pdf_valida = models.BooleanField(default=False, editable=False)
    paginas = models.PositiveIntegerField(blank=True, null=True, editable=False)
    paginas_amostradas = models.PositiveSmallIntegerField(default=0, editable=False)
    caracteres_amostra = models.PositiveIntegerField(default=0, editable=False)
    rota_sugerida = models.CharField(
        max_length=20,
        choices=RotaSugerida.choices,
        blank=True,
        editable=False,
    )
    texto_amostra = models.TextField(blank=True, editable=False)
    fontes_metadados = models.JSONField(default=dict, blank=True, editable=False)
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
    documento_principal_candidato = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="documentos_apoio",
        blank=True,
        null=True,
        verbose_name="documento principal confirmado",
        help_text="Vínculo aceito para o documento de apoio após revisão.",
    )
    documento_principal_sugerido = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="documentos_apoio_sugeridos",
        blank=True,
        null=True,
        editable=False,
        verbose_name="documento principal sugerido",
        help_text="Hipótese automática de vínculo; não autoriza confirmação.",
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
        ordering = ["indice_arquivo"]
        constraints = [
            models.UniqueConstraint(
                fields=["lote", "indice_arquivo"],
                name="item_importacao_indice_unico",
            )
        ]
        verbose_name = "item de importação"
        verbose_name_plural = "itens de importação"

    @staticmethod
    def normalizar_numero(valor: str) -> str:
        return "".join(caractere for caractere in valor if caractere.isdigit())

    def _erro_vinculo_principal(self, campo: str) -> str | None:
        relacionado_id = getattr(self, f"{campo}_id", None)
        if not relacionado_id:
            return None
        if self.pk and relacionado_id == self.pk:
            return "O item não pode apontar para si próprio."
        relacionado = getattr(self, campo)
        if self.lote_id and relacionado.lote_id != self.lote_id:
            return "O documento principal deve pertencer ao mesmo lote."
        if relacionado.natureza != self.Natureza.NORMATIVO_MUNICIPAL:
            return "O documento principal deve ser um ato normativo municipal."
        if relacionado.estado in {
            self.Estado.DUPLICADO,
            self.Estado.IGNORADO,
            self.Estado.FALHOU,
        }:
            return "O documento principal não pode estar duplicado, ignorado ou com falha."
        if not relacionado.assinatura_pdf_valida:
            return "O documento principal deve possuir assinatura PDF válida."
        obrigatorios = [
            relacionado.municipio_candidato,
            relacionado.uf,
            relacionado.tipo_normativo_codigo,
            relacionado.numero_normalizado or relacionado.numero_candidato,
            relacionado.ano_candidato,
        ]
        if not all(obrigatorios):
            return "O documento principal deve possuir metadados normativos mínimos."
        if (
            self.municipio_candidato
            and relacionado.municipio_candidato != self.municipio_candidato
        ):
            return "O documento principal deve pertencer ao mesmo município do item de apoio."
        return None

    def _validar_vinculo_principal(self, campo: str) -> None:
        if erro := self._erro_vinculo_principal(campo):
            raise ValidationError({campo: erro})

    def clean(self) -> None:
        super().clean()
        self.uf = self.uf.strip().upper()
        self.numero_normalizado = self.normalizar_numero(self.numero_candidato)
        self.numero_sugerido_normalizado = self.normalizar_numero(self.numero_sugerido_texto)
        if self.uf and len(self.uf) != 2:
            raise ValidationError({"uf": "Informe uma UF com duas letras."})
        if self.estado == self.Estado.PRONTO and not self.assinatura_pdf_valida:
            raise ValidationError(
                {"estado": "Um arquivo sem assinatura PDF válida não pode ser confirmado."}
            )
        self._validar_vinculo_principal("documento_principal_candidato")
        self._validar_vinculo_principal("documento_principal_sugerido")

    def save(self, *args, **kwargs) -> None:
        self.numero_normalizado = self.normalizar_numero(self.numero_candidato)
        self.numero_sugerido_normalizado = self.normalizar_numero(self.numero_sugerido_texto)
        if erro := self._erro_vinculo_principal("documento_principal_candidato"):
            raise ValidationError({"documento_principal_candidato": erro})
        if self._erro_vinculo_principal("documento_principal_sugerido"):
            self.documento_principal_sugerido = None
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.caminho_relativo
