# Generated manually for the auditable batch-ingestion increment.

import uuid

import django.db.models.deletion
from django.db import migrations, models

import ingestao.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [("applications", "0007_auditoria_corpus")]

    operations = [
        migrations.CreateModel(
            name="ImportacaoLote",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("titulo", models.CharField(max_length=200)),
                ("descricao", models.TextField(blank=True)),
                ("origem_recebimento", models.CharField(max_length=255)),
                ("uf_padrao", models.CharField(default="SP", max_length=2)),
                ("arquivo_zip", models.FileField(upload_to=ingestao.models.caminho_lote)),
                ("nome_original", models.CharField(blank=True, max_length=255)),
                ("sha256", models.CharField(db_index=True, editable=False, max_length=64)),
                (
                    "chave_idempotencia_sha256",
                    models.CharField(
                        blank=True,
                        editable=False,
                        max_length=64,
                        null=True,
                        unique=True,
                    ),
                ),
                ("tamanho_bytes", models.PositiveBigIntegerField(default=0, editable=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("recebido", "Recebido"),
                            ("inspecionando", "Inspecionando"),
                            ("inspecionado", "Inspecionado"),
                            ("confirmando", "Confirmando"),
                            ("confirmado", "Confirmado"),
                            ("falhou", "Falhou"),
                        ],
                        default="recebido",
                        max_length=20,
                    ),
                ),
                ("parametros", models.JSONField(blank=True, default=dict)),
                ("metricas", models.JSONField(blank=True, default=dict)),
                ("avisos", models.JSONField(blank=True, default=list)),
                ("mensagem_erro", models.TextField(blank=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("iniciado_em", models.DateTimeField(blank=True, null=True)),
                ("concluido_em", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "importação em lote",
                "verbose_name_plural": "importações em lote",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="ItemImportacaoLote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("indice_arquivo", models.PositiveIntegerField()),
                ("caminho_relativo", models.TextField()),
                ("nome_original", models.CharField(max_length=255)),
                ("municipio_candidato", models.CharField(blank=True, max_length=150)),
                ("uf", models.CharField(blank=True, max_length=2)),
                (
                    "natureza",
                    models.CharField(
                        choices=[
                            ("normativo_municipal", "Normativo municipal"),
                            ("normativo_estadual", "Normativo estadual"),
                            ("normativo_federal", "Normativo federal"),
                            ("plano_habitacional", "Plano habitacional"),
                            ("estudo_tecnico", "Estudo técnico"),
                            ("pagina_institucional", "Página institucional"),
                            ("diario_oficial", "Diário oficial"),
                            ("anexo_normativo", "Anexo normativo"),
                            ("fragmento_normativo", "Fragmento normativo"),
                            ("outro", "Outro documento de apoio"),
                        ],
                        default="outro",
                        max_length=32,
                    ),
                ),
                ("tipo_normativo_codigo", models.CharField(blank=True, max_length=60)),
                ("numero_candidato", models.CharField(blank=True, max_length=40)),
                ("ano_candidato", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("titulo_candidato", models.CharField(blank=True, max_length=255)),
                ("data_publicacao_candidata", models.DateField(blank=True, null=True)),
                ("sha256", models.CharField(db_index=True, max_length=64)),
                ("tamanho_bytes", models.PositiveBigIntegerField(default=0)),
                ("mime_type", models.CharField(default="application/pdf", max_length=120)),
                ("assinatura_pdf_valida", models.BooleanField(default=False, editable=False)),
                ("confianca", models.FloatField(default=0.0)),
                ("avisos", models.JSONField(blank=True, default=list)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("pronto", "Pronto para confirmar"),
                            ("revisao", "Revisão humana"),
                            ("duplicado", "Duplicado no lote"),
                            ("ignorado", "Ignorado"),
                            ("confirmado", "Confirmado"),
                            ("falhou", "Falhou"),
                        ],
                        default="revisao",
                        max_length=16,
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "documento_criado",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="itens_importacao",
                        to="applications.documentonormativo",
                    ),
                ),
                (
                    "duplicado_de",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="duplicatas",
                        to="ingestao.itemimportacaolote",
                    ),
                ),
                (
                    "lote",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="itens",
                        to="ingestao.importacaolote",
                    ),
                ),
                (
                    "versao_criada",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="itens_importacao",
                        to="applications.versaodocumento",
                    ),
                ),
            ],
            options={
                "verbose_name": "item de importação",
                "verbose_name_plural": "itens de importação",
                "ordering": ["indice_arquivo"],
            },
        ),
        migrations.AddConstraint(
            model_name="itemimportacaolote",
            constraint=models.UniqueConstraint(
                fields=("lote", "indice_arquivo"),
                name="item_importacao_indice_unico",
            ),
        ),
    ]
