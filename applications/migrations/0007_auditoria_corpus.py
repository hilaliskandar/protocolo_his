# Generated manually for the corpus-audit increment.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("applications", "0006_qualificacao_documental"),
    ]

    operations = [
        migrations.CreateModel(
            name="AtoNormativo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("identificador", models.SlugField(max_length=180, unique=True)),
                ("especie", models.CharField(blank=True, max_length=120)),
                ("numero", models.CharField(blank=True, max_length=40)),
                ("ano", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("data_norma", models.DateField(blank=True, null=True)),
                ("ementa", models.TextField(blank=True)),
                (
                    "natureza_texto",
                    models.CharField(
                        choices=[
                            ("original", "Original"),
                            ("modificador", "Ato modificador"),
                            ("consolidado_oficial", "Consolidado oficial"),
                            ("compilacao", "Compilação"),
                            ("nao_identificada", "Não identificada"),
                        ],
                        default="nao_identificada",
                        max_length=24,
                    ),
                ),
                ("pagina_inicial", models.PositiveIntegerField()),
                ("pagina_final", models.PositiveIntegerField()),
                ("primeiro_artigo", models.CharField(blank=True, max_length=40)),
                ("ultimo_artigo", models.CharField(blank=True, max_length=40)),
                (
                    "status_auditoria",
                    models.CharField(
                        choices=[
                            ("pendente", "Pendente"),
                            ("em_revisao", "Em revisão"),
                            ("aprovado", "Aprovado"),
                            ("reprovado", "Reprovado"),
                        ],
                        default="pendente",
                        max_length=16,
                    ),
                ),
                ("metadados", models.JSONField(blank=True, default=dict)),
                (
                    "versao_documento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="atos_normativos",
                        to="applications.versaodocumento",
                    ),
                ),
            ],
            options={
                "verbose_name": "ato normativo",
                "verbose_name_plural": "atos normativos",
                "ordering": ["versao_documento", "pagina_inicial", "identificador"],
            },
        ),
        migrations.CreateModel(
            name="ArtigoNormativo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("identificador", models.SlugField(max_length=220, unique=True)),
                ("rotulo", models.CharField(max_length=80)),
                ("numero_textual", models.CharField(max_length=40)),
                ("numero_normalizado", models.PositiveIntegerField(blank=True, null=True)),
                ("sufixo", models.CharField(blank=True, max_length=12)),
                ("pagina_inicial", models.PositiveIntegerField()),
                ("pagina_final", models.PositiveIntegerField()),
                ("heading_encontrado", models.BooleanField(default=True)),
                ("fonte_pos_bloco", models.BooleanField(default=False)),
                ("texto", models.TextField()),
                ("estrutura", models.JSONField(blank=True, default=dict)),
                ("sha256_texto", models.CharField(blank=True, db_index=True, editable=False, max_length=64)),
                (
                    "status_sequencia",
                    models.CharField(
                        choices=[
                            ("regular", "Regular"),
                            ("lacuna", "Lacuna"),
                            ("duplicado", "Duplicado"),
                            ("irregular_original", "Irregularidade original"),
                            ("nao_resolvido", "Não resolvido"),
                        ],
                        default="regular",
                        max_length=24,
                    ),
                ),
                (
                    "status_auditoria",
                    models.CharField(
                        choices=[
                            ("pendente", "Pendente"),
                            ("automatica", "Auditoria automática"),
                            ("revisado", "Revisado"),
                            ("adjudicado", "Adjudicado"),
                        ],
                        default="pendente",
                        max_length=16,
                    ),
                ),
                ("observacoes", models.TextField(blank=True)),
                (
                    "ato",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artigos",
                        to="applications.atonormativo",
                    ),
                ),
            ],
            options={
                "verbose_name": "artigo normativo",
                "verbose_name_plural": "artigos normativos",
                "ordering": ["ato", "pagina_inicial", "numero_normalizado", "sufixo", "pk"],
            },
        ),
        migrations.CreateModel(
            name="AnexoNormativo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("identificador", models.SlugField(max_length=220, unique=True)),
                ("titulo", models.CharField(max_length=255)),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("texto", "Texto"),
                            ("tabela", "Tabela"),
                            ("mapa", "Mapa"),
                            ("coordenadas", "Coordenadas"),
                            ("formulario", "Formulário"),
                            ("outro", "Outro"),
                        ],
                        max_length=20,
                    ),
                ),
                ("pagina_inicial", models.PositiveIntegerField(blank=True, null=True)),
                ("pagina_final", models.PositiveIntegerField(blank=True, null=True)),
                ("destino", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("identificado", "Identificado"),
                            ("extraido", "Extraído"),
                            ("revisado", "Revisado"),
                            ("pendente", "Pendente"),
                        ],
                        default="identificado",
                        max_length=16,
                    ),
                ),
                ("metadados", models.JSONField(blank=True, default=dict)),
                (
                    "artigo_referencia",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="anexos_referenciados",
                        to="applications.artigonormativo",
                    ),
                ),
                (
                    "ato",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="anexos",
                        to="applications.atonormativo",
                    ),
                ),
            ],
            options={
                "verbose_name": "anexo normativo",
                "verbose_name_plural": "anexos normativos",
                "ordering": ["ato", "pagina_inicial", "titulo"],
            },
        ),
        migrations.CreateModel(
            name="OcorrenciaDocumental",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("categoria", models.CharField(max_length=80)),
                (
                    "severidade",
                    models.CharField(
                        choices=[
                            ("critica", "Crítica"),
                            ("alta", "Alta"),
                            ("media", "Média"),
                            ("baixa", "Baixa"),
                        ],
                        max_length=12,
                    ),
                ),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("aberta", "Aberta"),
                            ("em_analise", "Em análise"),
                            ("resolvida", "Resolvida"),
                            ("aceita", "Aceita como irregularidade da fonte"),
                            ("nao_resolvida", "Não resolvida"),
                        ],
                        default="aberta",
                        max_length=20,
                    ),
                ),
                ("pagina", models.PositiveIntegerField(blank=True, null=True)),
                ("descricao", models.TextField()),
                ("evidencias", models.JSONField(blank=True, default=list)),
                ("decisao", models.TextField(blank=True)),
                ("resolvida_em", models.DateTimeField(blank=True, null=True)),
                (
                    "anexo",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ocorrencias",
                        to="applications.anexonormativo",
                    ),
                ),
                (
                    "artigo",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ocorrencias",
                        to="applications.artigonormativo",
                    ),
                ),
                (
                    "ato",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ocorrencias",
                        to="applications.atonormativo",
                    ),
                ),
                (
                    "resolvida_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ocorrencias_documentais_resolvidas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "versao_documento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ocorrencias_documentais",
                        to="applications.versaodocumento",
                    ),
                ),
            ],
            options={
                "verbose_name": "ocorrência documental",
                "verbose_name_plural": "ocorrências documentais",
                "ordering": ["-severidade", "estado", "versao_documento", "pagina", "pk"],
            },
        ),
        migrations.CreateModel(
            name="AdjudicacaoDocumental",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("decisao", models.TextField()),
                ("fundamento", models.TextField()),
                ("impacto", models.TextField(blank=True)),
                (
                    "estado_resultante",
                    models.CharField(
                        choices=[
                            ("aberta", "Aberta"),
                            ("em_analise", "Em análise"),
                            ("resolvida", "Resolvida"),
                            ("aceita", "Aceita como irregularidade da fonte"),
                            ("nao_resolvida", "Não resolvida"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "ocorrencia",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adjudicacao",
                        to="applications.ocorrenciadocumental",
                    ),
                ),
                (
                    "responsavel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="adjudicacoes_documentais",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "adjudicação documental",
                "verbose_name_plural": "adjudicações documentais",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="ReleaseCorpus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("versao", models.CharField(max_length=30)),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("rascunho", "Rascunho"),
                            ("em_validacao", "Em validação"),
                            ("liberado", "Liberado"),
                            ("substituido", "Substituído"),
                            ("revogado", "Revogado"),
                        ],
                        default="rascunho",
                        max_length=20,
                    ),
                ),
                (
                    "status_indexacao",
                    models.CharField(
                        choices=[
                            ("A", "A — pronto para indexação"),
                            ("B", "B — indexável com ressalvas"),
                            ("C", "C — não indexar"),
                        ],
                        default="C",
                        max_length=1,
                    ),
                ),
                (
                    "status_validacao",
                    models.CharField(
                        choices=[
                            ("V0", "V0 — não validado"),
                            ("V1", "V1 — exploração"),
                            ("V2", "V2 — análise técnica"),
                            ("V3", "V3 — benchmark ou uso sensível"),
                        ],
                        default="V0",
                        max_length=2,
                    ),
                ),
                ("protocolo_conversao", models.CharField(default="PCR-NORM-RAG v1.1", max_length=40)),
                ("manifesto_sha256", models.CharField(blank=True, db_index=True, max_length=64)),
                ("metricas", models.JSONField(blank=True, default=dict)),
                ("observacoes", models.TextField(blank=True)),
                ("liberado_em", models.DateTimeField(blank=True, null=True)),
                (
                    "aplicacao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="releases_corpus",
                        to="applications.aplicacaomunicipal",
                    ),
                ),
                (
                    "liberado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="releases_corpus_liberados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "release de corpus",
                "verbose_name_plural": "releases de corpus",
                "ordering": ["aplicacao", "-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="ReleaseCorpusDocumento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("incluído_em", models.DateTimeField(auto_now_add=True)),
                ("observacoes", models.TextField(blank=True)),
                (
                    "release",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documentos_release",
                        to="applications.releasecorpus",
                    ),
                ),
                (
                    "versao_documento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="vinculos_release",
                        to="applications.versaodocumento",
                    ),
                ),
            ],
            options={
                "verbose_name": "documento de release",
                "verbose_name_plural": "documentos de release",
                "ordering": ["release", "versao_documento"],
            },
        ),
        migrations.AddField(
            model_name="releasecorpus",
            name="versoes_documentais",
            field=models.ManyToManyField(
                related_name="releases_corpus",
                through="applications.ReleaseCorpusDocumento",
                to="applications.versaodocumento",
            ),
        ),
        migrations.AddConstraint(
            model_name="atonormativo",
            constraint=models.CheckConstraint(
                condition=Q(pagina_final__gte=models.F("pagina_inicial")),
                name="ato_pagina_final_maior_igual_inicial",
            ),
        ),
        migrations.AddConstraint(
            model_name="atonormativo",
            constraint=models.UniqueConstraint(
                fields=("versao_documento", "pagina_inicial", "pagina_final"),
                name="ato_intervalo_unico_por_versao",
            ),
        ),
        migrations.AddConstraint(
            model_name="artigonormativo",
            constraint=models.CheckConstraint(
                condition=Q(pagina_final__gte=models.F("pagina_inicial")),
                name="artigo_pagina_final_maior_igual_inicial",
            ),
        ),
        migrations.AddConstraint(
            model_name="artigonormativo",
            constraint=models.UniqueConstraint(
                fields=("ato", "numero_textual", "sufixo"),
                name="artigo_numero_sufixo_unico_por_ato",
            ),
        ),
        migrations.AddConstraint(
            model_name="anexonormativo",
            constraint=models.CheckConstraint(
                condition=Q(pagina_final__isnull=True)
                | Q(pagina_inicial__isnull=True)
                | Q(pagina_final__gte=models.F("pagina_inicial")),
                name="anexo_pagina_final_maior_igual_inicial",
            ),
        ),
        migrations.AddConstraint(
            model_name="releasecorpus",
            constraint=models.UniqueConstraint(
                fields=("aplicacao", "versao"),
                name="release_versao_unica_por_aplicacao",
            ),
        ),
        migrations.AddConstraint(
            model_name="releasecorpusdocumento",
            constraint=models.UniqueConstraint(
                fields=("release", "versao_documento"),
                name="release_documento_unico",
            ),
        ),
    ]
