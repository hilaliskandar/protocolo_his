import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ingestao", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="itemimportacaolote",
            name="caracteres_amostra",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="fontes_metadados",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="numero_normalizado",
            field=models.CharField(blank=True, db_index=True, max_length=40),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="paginas",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="paginas_amostradas",
            field=models.PositiveSmallIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="rota_sugerida",
            field=models.CharField(
                blank=True,
                choices=[
                    ("texto_nativo", "Texto nativo"),
                    ("ocr", "OCR"),
                    ("misto", "Misto"),
                    ("manual", "Revisão manual"),
                ],
                editable=False,
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="texto_amostra",
            field=models.TextField(blank=True, editable=False),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="documento_principal_candidato",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="documentos_apoio",
                to="ingestao.itemimportacaolote",
            ),
        ),
    ]
