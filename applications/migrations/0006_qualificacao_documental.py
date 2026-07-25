# Generated manually for the qualification-document increment.

import django.db.models.deletion
from django.db import migrations, models

import applications.models


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0005_geometrias_municipais"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessamentoDocumento",
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
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "etapa",
                    models.CharField(
                        choices=[
                            ("qualificacao", "Qualificação documental"),
                            ("conversao", "Conversão"),
                            ("validacao", "Validação"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pendente", "Pendente"),
                            ("em_execucao", "Em execução"),
                            ("concluido", "Concluído"),
                            ("falhou", "Falhou"),
                        ],
                        default="pendente",
                        max_length=20,
                    ),
                ),
                (
                    "rota_documento",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("texto_nativo", "Texto nativo"),
                            ("ocr", "OCR"),
                            ("misto", "Misto"),
                            ("visual_complexo", "Visual complexo"),
                            ("manual", "Revisão manual"),
                        ],
                        max_length=24,
                    ),
                ),
                ("ferramenta", models.CharField(max_length=120)),
                ("versao_ferramenta", models.CharField(blank=True, max_length=80)),
                ("versao_codigo", models.CharField(blank=True, max_length=64)),
                ("parametros", models.JSONField(blank=True, default=dict)),
                ("metricas", models.JSONField(blank=True, default=dict)),
                ("avisos", models.JSONField(blank=True, default=list)),
                ("mensagem_erro", models.TextField(blank=True)),
                ("iniciado_em", models.DateTimeField(blank=True, null=True)),
                ("concluido_em", models.DateTimeField(blank=True, null=True)),
                ("duracao_segundos", models.FloatField(blank=True, null=True)),
                (
                    "versao_documento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="processamentos",
                        to="applications.versaodocumento",
                    ),
                ),
            ],
            options={
                "verbose_name": "processamento documental",
                "verbose_name_plural": "processamentos documentais",
                "ordering": ["-criado_em", "-pk"],
            },
        ),
        migrations.CreateModel(
            name="DiagnosticoPagina",
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
                ("numero_pagina", models.PositiveIntegerField()),
                ("rota", models.CharField(max_length=24)),
                ("tipo_pagina", models.CharField(max_length=40)),
                ("possui_texto_nativo", models.BooleanField(default=False)),
                ("quantidade_caracteres", models.PositiveIntegerField(default=0)),
                ("quantidade_imagens", models.PositiveIntegerField(default=0)),
                ("tabela_suspeita", models.BooleanField(default=False)),
                ("mapa_suspeito", models.BooleanField(default=False)),
                ("modo_extracao", models.CharField(blank=True, max_length=40)),
                ("texto_rotacionado", models.BooleanField(default=False)),
                ("avisos", models.JSONField(blank=True, default=list)),
                ("dados_tecnicos", models.JSONField(blank=True, default=dict)),
                (
                    "processamento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="diagnosticos_paginas",
                        to="applications.processamentodocumento",
                    ),
                ),
            ],
            options={
                "verbose_name": "diagnóstico de página",
                "verbose_name_plural": "diagnósticos de páginas",
                "ordering": ["processamento", "numero_pagina"],
            },
        ),
        migrations.CreateModel(
            name="ArtefatoProcessado",
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
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("diagnostico_json", "Diagnóstico JSON"),
                            ("markdown", "Markdown"),
                            ("log", "Log"),
                            ("outro", "Outro"),
                        ],
                        max_length=24,
                    ),
                ),
                (
                    "arquivo",
                    models.FileField(upload_to=applications.models.caminho_artefato_processado),
                ),
                ("sha256", models.CharField(db_index=True, editable=False, max_length=64)),
                ("tamanho_bytes", models.PositiveBigIntegerField(editable=False)),
                ("mime_type", models.CharField(max_length=120)),
                ("metadados", models.JSONField(blank=True, default=dict)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "processamento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artefatos",
                        to="applications.processamentodocumento",
                    ),
                ),
            ],
            options={
                "verbose_name": "artefato processado",
                "verbose_name_plural": "artefatos processados",
                "ordering": ["processamento", "tipo"],
            },
        ),
        migrations.AddConstraint(
            model_name="diagnosticopagina",
            constraint=models.UniqueConstraint(
                fields=("processamento", "numero_pagina"),
                name="diagnostico_pagina_unico_processamento",
            ),
        ),
        migrations.AddConstraint(
            model_name="artefatoprocessado",
            constraint=models.UniqueConstraint(
                fields=("processamento", "tipo"),
                name="artefato_tipo_unico_processamento",
            ),
        ),
    ]
