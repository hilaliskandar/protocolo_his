import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("applications", "0007_auditoria_corpus"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClassificacaoVersao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("natureza", models.CharField(choices=[("texto_original", "Texto original"), ("consolidacao_oficial", "Consolidação oficial"), ("republicacao", "Republicação"), ("retificacao", "Retificação"), ("copia", "Cópia"), ("indeterminada", "Indeterminada")], default="indeterminada", max_length=24)),
                ("data_referencia_normativa", models.DateField(blank=True, null=True)),
                ("referencia_atualizacao", models.CharField(blank=True, max_length=255)),
                ("estado", models.CharField(choices=[("pendente", "Pendente"), ("confirmada", "Confirmada"), ("rejeitada", "Rejeitada")], default="pendente", max_length=16)),
                ("justificativa", models.TextField(blank=True)),
                ("fonte", models.CharField(blank=True, max_length=255)),
                ("confirmado_em", models.DateTimeField(blank=True, null=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("confirmado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="classificacoes_versao_confirmadas", to=settings.AUTH_USER_MODEL)),
                ("versao_documento", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="classificacao_normativa", to="applications.versaodocumento")),
            ],
            options={
                "verbose_name": "classificação de versão normativa",
                "verbose_name_plural": "classificações de versões normativas",
                "ordering": ["versao_documento"],
            },
        ),
        migrations.CreateModel(
            name="RelacaoVersoes",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("sucessao", "Sucessão"), ("equivalencia", "Equivalência"), ("derivacao", "Derivação")], max_length=16)),
                ("estado", models.CharField(choices=[("pendente", "Pendente"), ("confirmada", "Confirmada"), ("rejeitada", "Rejeitada")], default="pendente", max_length=16)),
                ("justificativa", models.TextField()),
                ("fonte", models.CharField(blank=True, max_length=255)),
                ("validado_em", models.DateTimeField(blank=True, null=True)),
                ("metadados", models.JSONField(blank=True, default=dict)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("validado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="relacoes_versoes_validadas", to=settings.AUTH_USER_MODEL)),
                ("versao_destino", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="relacoes_como_destino", to="applications.versaodocumento")),
                ("versao_origem", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="relacoes_como_origem", to="applications.versaodocumento")),
            ],
            options={
                "verbose_name": "relação entre versões normativas",
                "verbose_name_plural": "relações entre versões normativas",
                "ordering": ["versao_origem", "versao_destino", "tipo"],
            },
        ),
        migrations.AddConstraint(
            model_name="relacaoversoes",
            constraint=models.CheckConstraint(condition=~Q(versao_origem=F("versao_destino")), name="relacao_versoes_origem_destino_distintos"),
        ),
        migrations.AddConstraint(
            model_name="relacaoversoes",
            constraint=models.UniqueConstraint(fields=("versao_origem", "versao_destino", "tipo"), name="relacao_versoes_unica_por_tipo"),
        ),
    ]
