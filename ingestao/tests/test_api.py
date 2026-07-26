from io import BytesIO
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from applications.models import DocumentoNormativo, TipoNormativo, VersaoDocumento
from ingestao.models import ImportacaoLote, ItemImportacaoLote

TOKEN = "segredo-de-teste"
CABECALHO = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


def zip_teste() -> bytes:
    memoria = BytesIO()
    with ZipFile(memoria, "w", ZIP_DEFLATED) as zip_file:
        pdf = b"%PDF-1.4\nconteudo de teste\n%%EOF"
        zip_file.writestr("Lote/Jundiaí/Plano Diretor/Lei-7016-2008.pdf", pdf)
        zip_file.writestr("Lote/Jundiaí/copia-Lei-7016-2008.pdf", pdf)
        zip_file.writestr("Lote/Jundiaí/PLHIS Produto 1.pdf", b"%PDF-1.4\nplhis\n%%EOF")
        zip_file.writestr("Lote/Jundiaí/Lei-9999-2020.pdf", b"nao e pdf")
    return memoria.getvalue()


def zip_com_caminhos_repetidos() -> bytes:
    memoria = BytesIO()
    with ZipFile(memoria, "w", ZIP_DEFLATED) as zip_file:
        zip_file.writestr("Lote/Jarinu/Lei-1-2020.pdf", b"%PDF-1.4\nprimeiro\n%%EOF")
        zip_file.writestr("Lote/Jarinu/Lei-1-2020.pdf", b"%PDF-1.4\nsegundo\n%%EOF")
    return memoria.getvalue()


@override_settings(API_INGESTAO_TOKEN=TOKEN, INGESTAO_CONFIANCA_AUTOMATICA=0.8)
class TestesApiIngestao(TestCase):
    def setUp(self):
        self.diretorio = TemporaryDirectory()
        self.settings = override_settings(
            MEDIA_ROOT=self.diretorio.name,
            PROTOCOL_DATA_ROOT=self.diretorio.name,
        )
        self.settings.enable()
        TipoNormativo.objects.get_or_create(
            codigo="lei_ordinaria",
            defaults={
                "nome": "Lei ordinária",
                "sigla": "LEI",
                "esfera": TipoNormativo.Esfera.MUNICIPAL,
                "fonte_normativa": "https://example.test/tipos/lei-ordinaria",
                "dispositivo_fonte": "teste automatizado",
            },
        )

    def tearDown(self):
        self.settings.disable()
        self.diretorio.cleanup()

    def _receber(self, conteudo: bytes | None = None, **headers):
        upload = SimpleUploadedFile(
            "canario.zip",
            conteudo or zip_teste(),
            "application/zip",
        )
        return self.client.post(
            reverse("api_criar_importacao"),
            {
                "arquivo_zip": upload,
                "titulo": "Canário RM Jundiaí",
                "origem_recebimento": "teste automatizado",
                "uf_padrao": "SP",
            },
            **CABECALHO,
            **headers,
        )

    def test_api_exige_autenticacao(self):
        resposta = self.client.post(reverse("api_criar_importacao"))
        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(resposta["WWW-Authenticate"], "Bearer")

    def test_recebimento_e_idempotente(self):
        resposta = self._receber(HTTP_IDEMPOTENCY_KEY="lote-jundiai-001")
        self.assertEqual(resposta.status_code, 201)
        resposta = self._receber(HTTP_IDEMPOTENCY_KEY="lote-jundiai-001")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["reutilizado"])
        self.assertEqual(ImportacaoLote.objects.count(), 1)

    def test_fluxo_receber_inspecionar_corrigir_e_confirmar(self):
        resposta = self._receber()
        self.assertEqual(resposta.status_code, 201)
        lote = ImportacaoLote.objects.get()
        resposta = self.client.post(
            reverse("api_inspecionar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 200)
        lote.refresh_from_db()
        self.assertEqual(lote.status, ImportacaoLote.Status.INSPECIONADO)
        self.assertEqual(lote.itens.count(), 4)
        self.assertEqual(
            lote.itens.filter(estado=ItemImportacaoLote.Estado.DUPLICADO).count(),
            1,
        )
        item = lote.itens.get(nome_original="Lei-7016-2008.pdf")
        self.assertEqual(item.municipio_candidato, "Jundiaí")
        self.assertTrue(item.assinatura_pdf_valida)
        if item.estado != ItemImportacaoLote.Estado.PRONTO:
            resposta = self.client.patch(
                reverse("api_atualizar_item_importacao", kwargs={"item_id": item.pk}),
                data={
                    "municipio_candidato": "Jundiaí",
                    "uf": "SP",
                    "natureza": "normativo_municipal",
                    "tipo_normativo_codigo": "lei_ordinaria",
                    "numero_candidato": "7016",
                    "ano_candidato": 2008,
                    "titulo_candidato": "Política Municipal de Habitação",
                    "estado": "pronto",
                },
                content_type="application/json",
                **CABECALHO,
            )
            self.assertEqual(resposta.status_code, 200)
        resposta = self.client.post(
            reverse("api_confirmar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(DocumentoNormativo.objects.count(), 1)
        self.assertEqual(VersaoDocumento.objects.count(), 1)
        versao = VersaoDocumento.objects.get()
        self.assertTrue(versao.sha256)
        self.assertEqual(versao.nome_original, "Lei-7016-2008.pdf")
        lote.refresh_from_db()
        self.assertEqual(lote.status, ImportacaoLote.Status.INSPECIONADO)
        resposta = self.client.post(
            reverse("api_confirmar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(VersaoDocumento.objects.count(), 1)

    def test_pdf_com_assinatura_invalida_nao_pode_ser_marcado_pronto(self):
        self._receber()
        lote = ImportacaoLote.objects.get()
        self.client.post(
            reverse("api_inspecionar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        item = lote.itens.get(nome_original="Lei-9999-2020.pdf")
        resposta = self.client.patch(
            reverse("api_atualizar_item_importacao", kwargs={"item_id": item.pk}),
            data={
                "municipio_candidato": "Jundiaí",
                "uf": "SP",
                "natureza": "normativo_municipal",
                "tipo_normativo_codigo": "lei_ordinaria",
                "numero_candidato": "9999",
                "ano_candidato": 2020,
                "titulo_candidato": "Arquivo inválido",
                "estado": "pronto",
            },
            content_type="application/json",
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.estado, ItemImportacaoLote.Estado.REVISAO)

    def test_caminhos_repetidos_no_zip_sao_preservados_por_indice(self):
        resposta = self._receber(zip_com_caminhos_repetidos())
        self.assertEqual(resposta.status_code, 201)
        lote = ImportacaoLote.objects.get()
        resposta = self.client.post(
            reverse("api_inspecionar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(lote.itens.count(), 2)
        self.assertEqual(
            list(lote.itens.order_by("indice_arquivo").values_list("indice_arquivo", flat=True)),
            [0, 1],
        )
        self.assertEqual(lote.itens.values("caminho_relativo").distinct().count(), 1)
