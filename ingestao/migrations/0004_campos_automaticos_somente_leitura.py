import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ingestao", "0003_sugestoes_metadados_e_vinculos")]

    operations = [
        migrations.AlterField(
            model_name="itemimportacaolote",
            name="ano_sugerido_texto",
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="itemimportacaolote",
            name="divergencias_metadados",
            field=models.JSONField(blank=True, default=list, editable=False),
        ),
        migrations.AlterField(
            model_name="itemimportacaolote",
            name="documento_principal_sugerido",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                help_text="Hipótese automática de vínculo; não autoriza confirmação.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="documentos_apoio_sugeridos",
                to="ingestao.itemimportacaolote",
                verbose_name="documento principal sugerido",
            ),
        ),
        migrations.AlterField(
            model_name="itemimportacaolote",
            name="fontes_metadados",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
        migrations.AlterField(
            model_name="itemimportacaolote",
            name="fontes_sugestoes",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
        migrations.AlterField(
            model_name="itemimportacaolote",
            name="numero_sugerido_normalizado",
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=40),
        ),
        migrations.AlterField(
            model_name="itemimportacaolote",
            name="numero_sugerido_texto",
            field=models.CharField(blank=True, editable=False, max_length=40),
        ),
    ]
