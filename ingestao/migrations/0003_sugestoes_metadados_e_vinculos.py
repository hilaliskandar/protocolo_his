import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ingestao", "0002_enriquecimento_manifesto")]

    operations = [
        migrations.AddField(
            model_name="itemimportacaolote",
            name="ano_sugerido_texto",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="divergencias_metadados",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="fontes_sugestoes",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="numero_sugerido_normalizado",
            field=models.CharField(blank=True, db_index=True, max_length=40),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="numero_sugerido_texto",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="itemimportacaolote",
            name="documento_principal_sugerido",
            field=models.ForeignKey(
                blank=True,
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
            name="documento_principal_candidato",
            field=models.ForeignKey(
                blank=True,
                help_text="Vínculo aceito para o documento de apoio após revisão.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="documentos_apoio",
                to="ingestao.itemimportacaolote",
                verbose_name="documento principal confirmado",
            ),
        ),
    ]
