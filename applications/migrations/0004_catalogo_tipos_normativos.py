from django.db import migrations, models
import django.db.models.deletion


FONTE_LC95 = "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp95compilado.htm"

TIPOS = (
    {
        "codigo": "emenda_constitucional",
        "nome": "Emenda constitucional",
        "sigla": "EC",
        "esfera": "federal",
        "dispositivo_fonte": "LC nº 95/1998, art. 1º, parágrafo único, c/c CF, art. 59",
        "ordem_exibicao": 10,
    },
    {
        "codigo": "lei_complementar",
        "nome": "Lei complementar",
        "sigla": "LC",
        "esfera": "geral",
        "dispositivo_fonte": "LC nº 95/1998, arts. 1º e 2º, § 2º, II",
        "ordem_exibicao": 20,
    },
    {
        "codigo": "lei_ordinaria",
        "nome": "Lei ordinária",
        "sigla": "LO",
        "esfera": "geral",
        "dispositivo_fonte": "LC nº 95/1998, arts. 1º e 2º, § 2º, II",
        "ordem_exibicao": 30,
    },
    {
        "codigo": "lei_delegada",
        "nome": "Lei delegada",
        "sigla": "LD",
        "esfera": "federal",
        "dispositivo_fonte": "LC nº 95/1998, art. 2º, § 2º, II",
        "ordem_exibicao": 40,
    },
    {
        "codigo": "medida_provisoria",
        "nome": "Medida provisória",
        "sigla": "MP",
        "esfera": "federal",
        "dispositivo_fonte": "LC nº 95/1998, art. 1º, parágrafo único",
        "ordem_exibicao": 50,
    },
    {
        "codigo": "decreto_legislativo",
        "nome": "Decreto legislativo",
        "sigla": "DL",
        "esfera": "geral",
        "dispositivo_fonte": "LC nº 95/1998, art. 1º, parágrafo único, c/c CF, art. 59",
        "ordem_exibicao": 60,
    },
    {
        "codigo": "resolucao",
        "nome": "Resolução",
        "sigla": "RES",
        "esfera": "geral",
        "dispositivo_fonte": "LC nº 95/1998, art. 1º, parágrafo único, c/c CF, art. 59",
        "ordem_exibicao": 70,
    },
    {
        "codigo": "decreto_regulamentar",
        "nome": "Decreto regulamentar",
        "sigla": "DEC",
        "esfera": "geral",
        "dispositivo_fonte": "LC nº 95/1998, art. 1º, parágrafo único",
        "ordem_exibicao": 80,
    },
    {
        "codigo": "outro_ato_regulamentar",
        "nome": "Outro ato regulamentar",
        "sigla": "",
        "esfera": "geral",
        "dispositivo_fonte": "LC nº 95/1998, art. 1º, parágrafo único",
        "ordem_exibicao": 90,
    },
)

MAPEAMENTO_LEGADO = {
    "lei": "lei_ordinaria",
    "lei_complementar": "lei_complementar",
    "decreto": "decreto_regulamentar",
    "resolucao": "resolucao",
    "outro": "outro_ato_regulamentar",
}


def carregar_tipos(apps, schema_editor):
    TipoNormativo = apps.get_model("applications", "TipoNormativo")
    DocumentoNormativo = apps.get_model("applications", "DocumentoNormativo")

    tipos_por_codigo = {}
    for dados in TIPOS:
        tipo, _ = TipoNormativo.objects.update_or_create(
            codigo=dados["codigo"],
            defaults={
                **dados,
                "fonte_normativa": FONTE_LC95,
                "ativo": True,
                "observacoes": "Catálogo inicial; complementar com fontes próprias da jurisdição.",
            },
        )
        tipos_por_codigo[dados["codigo"]] = tipo

    for documento in DocumentoNormativo.objects.all().iterator():
        codigo = MAPEAMENTO_LEGADO.get(documento.tipo, "outro_ato_regulamentar")
        documento.tipo_referencia = tipos_por_codigo[codigo]
        documento.save(update_fields=["tipo_referencia"])


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0003_municipios_ibge"),
    ]

    operations = [
        migrations.CreateModel(
            name="TipoNormativo",
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
                ("codigo", models.SlugField(max_length=60, unique=True)),
                ("nome", models.CharField(max_length=150)),
                ("sigla", models.CharField(blank=True, max_length=20)),
                (
                    "esfera",
                    models.CharField(
                        choices=[
                            ("geral", "Geral"),
                            ("federal", "Federal"),
                            ("estadual", "Estadual"),
                            ("municipal", "Municipal"),
                        ],
                        default="geral",
                        max_length=12,
                    ),
                ),
                ("fonte_normativa", models.URLField()),
                ("dispositivo_fonte", models.CharField(max_length=255)),
                ("observacoes", models.TextField(blank=True)),
                ("ativo", models.BooleanField(default=True)),
                ("ordem_exibicao", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "verbose_name": "tipo normativo",
                "verbose_name_plural": "tipos normativos",
                "ordering": ["ordem_exibicao", "nome"],
            },
        ),
        migrations.AddField(
            model_name="documentonormativo",
            name="tipo_referencia",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documentos_em_migracao",
                to="applications.tiponormativo",
            ),
        ),
        migrations.RunPython(carregar_tipos, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="documentonormativo",
            name="documento_identidade_unica_aplicacao",
        ),
        migrations.RemoveField(
            model_name="documentonormativo",
            name="tipo",
        ),
        migrations.RenameField(
            model_name="documentonormativo",
            old_name="tipo_referencia",
            new_name="tipo",
        ),
        migrations.AlterField(
            model_name="documentonormativo",
            name="tipo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documentos",
                to="applications.tiponormativo",
            ),
        ),
        migrations.AddConstraint(
            model_name="documentonormativo",
            constraint=models.UniqueConstraint(
                fields=("aplicacao", "tipo", "numero", "ano"),
                name="documento_identidade_unica_aplicacao",
            ),
        ),
        migrations.AlterModelOptions(
            name="documentonormativo",
            options={
                "ordering": ["ano", "numero"],
                "verbose_name": "documento normativo",
                "verbose_name_plural": "documentos normativos",
            },
        ),
    ]
