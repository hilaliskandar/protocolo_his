from io import BytesIO
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from applications.models import DocumentoNormativo, VersaoDocumento
from ingestao.models import ImportacaoLote, ItemImportacaoLote

TOKEN = "segredo-de-teste"
CABECALHO = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


def zip_teste() -> bytes:
    memoria = BytesIO()
    with ZipFile(memoria, "w", ZIP_DEFLATED) as zip_file:
        pdf = b"%PDF-1.4\nconteudo de teste\n%%EOF"
        zip_file.writestr("Lote/Jundiaí/Lei-7016-2008.pdf", pdf)
        zip_file.writestr("Lote/Jundiaí/copia-Lei-7016-2008.pdf", pdf)
        zip_file.writestr("Lote/Jundiaí/PLHIS Produto 1.pdf", b"%PDF-1.4\nplhis\n%%EOF")
    return memoria.getvalue()


@override_settings(API_INGESTAO_TOKEN=TOKEN, INGESTAO_CONFIANCA_AUTOMATICA=0.8)
class TestesApiIngestao(TestCase):
    def setUp(self):
        self.diretorio = TemporaryDirectory()
        self.settings = override_settings(MEDIA_ROOT=self.diretorio.name, PROTOCOL_DATA_ROOT=self.diretorio.name)
        self.settings.enable()

    def tearDown(self):
        self.settings.disable()
        self.diretorio.cleanup()

    def test_api_exige_autenticacao(self):
        resposta = self.client.post(reverse("api_criar_importacao"))
        self.assertEqual(resposta.status_code, 401)

    def test_fluxo_receber_inspecionar_corrigir_e_confirmar(self):
        upload = SimpleUploadedFile("canario.zip", zip_teste(), "application/zip")
        resposta = self.client.post(
            reverse("api_criar_importacao"),
            {"arquivo_zip": upload, "titulo": "Canário RM Jundiaí", "origem_recebimento": "teste automatizado", "uf_padrao": "SP"},
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 201)
        lote = ImportacaoLote.objects.get()
        resposta = self.client.post(reverse("api_inspecionar_importacao", kwargs={"lote_id": lote.pk}), **CABECALHO)
        self.assertEqual(resposta.status_code, 200)
        lote.refresh_from_db()
        self.assertEqual(lote.status, ImportacaoLote.Status.INSPECIONADO)
        self.assertEqual(lote.itens.count(), 3)
        self.assertEqual(lote.itens.filter(estado=ItemImportacaoLote.Estado.DUPLICADO).count(), 1)
        item = lote.itens.get(nome_original="Lei-7016-2008.pdf")
        if item.estado != ItemImportacaoLote.Estado.PRONTO:
            resposta = self.client.patch(
                reverse("api_atualizar_item_importacao", kwargs={"item_id": item.pk}),
                data={"municipio_candidato": "Jundiaí", "uf": "SP", "natureza": "normativo_municipal", "tipo_normativo_codigo": "lei_ordinaria", "numero_candidato": "7016", "ano_candidato": 2008, "titulo_candidato": "Política Municipal de Habitação", "estado": "pronto"},
                content_type="application/json",
                **CABECALHO,
            )
            self.assertEqual(resposta.status_code, 200)
        resposta = self.client.post(reverse("api_confirmar_importacao", kwargs={"lote_id": lote.pk}), **CABECALHO)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(DocumentoNormativo.objects.count(), 1)
        self.assertEqual(VersaoDocumento.objects.count(), 1)
        versao = VersaoDocumento.objects.get()
        self.assertTrue(versao.sha256)
        self.assertEqual(versao.nome_original, "Lei-7016-2008.pdf")
