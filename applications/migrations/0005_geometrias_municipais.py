from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0004_catalogo_tipos_normativos"),
    ]

    operations = [
        migrations.AddField(
            model_name="municipio",
            name="data_referencia_geometria",
            field=models.DateField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="municipio",
            name="fonte_geometria",
            field=models.URLField(blank=True, editable=False),
        ),
        migrations.AddField(
            model_name="municipio",
            name="geometria_atualizada_em",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="municipio",
            name="geometria_geojson",
            field=models.JSONField(
                blank=True,
                editable=False,
                null=True,
                verbose_name="geometria GeoJSON",
            ),
        ),
        migrations.AddField(
            model_name="municipio",
            name="sha256_geometria",
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
    ]
