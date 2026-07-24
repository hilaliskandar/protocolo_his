# Generated for the Protocolo HIS MVP foundation.

import applications.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Municipio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("nome", models.CharField(max_length=150)),
                ("uf", models.CharField(max_length=2, verbose_name="UF")),
                ("codigo_ibge", models.CharField(blank=True, max_length=7, null=True, unique=True, verbose_name="código IBGE")),
            ],
            options={
                "verbose_name": "município",
                "verbose_name_plural": "municípios",
                "ordering": ["uf", "nome"],
            },
        ),
        migrations.CreateModel(
            name="AplicacaoMunicipal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("titulo", models.CharField(max_length=200)),
                ("descricao", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("rascunho", "Rascunho"), ("corpus_recebido", "Corpus recebido"), ("corpus_liberado", "Corpus liberado"), ("em_analise", "Em análise"), ("em_validacao", "Em validação"), ("concluida", "Concluída")], default="rascunho", max_length=24)),
                ("municipio", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="aplicacoes", to="applications.municipio")),
            ],
            options={
                "verbose_name": "aplicação municipal",
                "verbose_name_plural": "aplicações municipais",
                "ordering": ["-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="DocumentoNormativo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("tipo", models.CharField(choices=[("lei", "Lei"), ("lei_complementar", "Lei complementar"), ("decreto", "Decreto"), ("resolucao", "Resolução"), ("outro", "Outro")], max_length=24)),
                ("numero", models.CharField(max_length=40)),
                ("ano", models.PositiveSmallIntegerField()),
                ("titulo", models.CharField(max_length=255)),
                ("data_publicacao", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("recebido", "Recebido"), ("verificado", "Verificado"), ("quarentena", "Em quarentena"), ("liberado", "Liberado para análise")], default="recebido", max_length=16)),
                ("aplicacao", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documentos", to="applications.aplicacaomunicipal")),
            ],
            options={
                "verbose_name": "documento normativo",
                "verbose_name_plural": "documentos normativos",
                "ordering": ["tipo", "ano", "numero"],
            },
        ),
        migrations.CreateModel(
            name="VersaoDocumento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("versao", models.PositiveSmallIntegerField(default=1)),
                ("arquivo", models.FileField(upload_to=applications.models.caminho_arquivo_documento)),
                ("nome_original", models.CharField(blank=True, max_length=255)),
                ("mime_type", models.CharField(blank=True, max_length=120)),
                ("sha256", models.CharField(db_index=True, editable=False, max_length=64)),
                ("tamanho_bytes", models.PositiveBigIntegerField(default=0, editable=False)),
                ("original_preservado", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("documento", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="versoes", to="applications.documentonormativo")),
            ],
            options={
                "verbose_name": "versão documental",
                "verbose_name_plural": "versões documentais",
                "ordering": ["documento", "versao"],
            },
        ),
        migrations.AddConstraint(
            model_name="municipio",
            constraint=models.UniqueConstraint(fields=("nome", "uf"), name="municipio_nome_uf_unicos"),
        ),
        migrations.AddConstraint(
            model_name="documentonormativo",
            constraint=models.UniqueConstraint(fields=("aplicacao", "tipo", "numero", "ano"), name="documento_identidade_unica_aplicacao"),
        ),
        migrations.AddConstraint(
            model_name="versaodocumento",
            constraint=models.UniqueConstraint(fields=("documento", "versao"), name="versao_unica_por_documento"),
        ),
    ]
