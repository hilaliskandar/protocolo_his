from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0002_inventario_corpus"),
    ]

    operations = [
        migrations.AddField(
            model_name="municipio",
            name="ativo",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="municipio",
            name="codigo_uf",
            field=models.CharField(blank=True, max_length=2, verbose_name="código da UF"),
        ),
        migrations.AddField(
            model_name="municipio",
            name="data_referencia",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="municipio",
            name="fonte_dados",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="municipio",
            name="nome_uf",
            field=models.CharField(blank=True, max_length=50, verbose_name="nome da UF"),
        ),
        migrations.AddField(
            model_name="municipio",
            name="sha256_fonte",
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
    ]
