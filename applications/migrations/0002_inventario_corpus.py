from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="versaodocumento",
            name="duplicado_de",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="duplicatas",
                to="applications.versaodocumento",
            ),
        ),
        migrations.AddField(
            model_name="versaodocumento",
            name="observacoes_ingestao",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="versaodocumento",
            name="origem_recebimento",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="versaodocumento",
            name="situacao_ingestao",
            field=models.CharField(
                choices=[("original", "Original"), ("duplicado", "Duplicado")],
                default="original",
                editable=False,
                max_length=16,
            ),
        ),
    ]
