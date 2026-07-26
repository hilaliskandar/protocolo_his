from io import BytesIO
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ingestao.models import ImportacaoLote

TOKEN = "segredo-seguranca"
CABECALHO = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


def montar_zip(nome: str, conteudo: bytes) -> bytes:
    memoria = BytesIO()
    with ZipFile(memoria, "w", ZIP_DEFLATED) as zip_file:
        zip_file.writestr(nome, conteudo)
    return memoria.getvalue()


@override_settings(API_INGESTAO_TOKEN=TOKEN)
class TestesSegurancaIngestao(TestCase):
    def setUp(self):
        self.diretorio = TemporaryDirectory()
        self.settings = override_settings(MEDIA_ROOT=self.diretorio.name)
        self.settings.enable()

    def tearDown(self):
        self.settings.disable()
        self.diretorio.cleanup()

    def _receber(self, conteudo: bytes) -> ImportacaoLote:
        resposta = self.client.post(
            reverse("api_criar_importacao"),
            {
                "arquivo_zip": SimpleUploadedFile("lote.zip", conteudo, "application/zip"),
                "titulo": "Lote de segurança",
                "origem_recebimento": "teste",
            },
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 201)
        return ImportacaoLote.objects.latest("criado_em")

    def test_caminho_com_travessia_e_ignorado(self):
        lote = self._receber(montar_zip("../fora.pdf", b"%PDF-1.4\n%%EOF"))
        resposta = self.client.post(
            reverse("api_inspecionar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 200)
        lote.refresh_from_db()
        self.assertEqual(lote.itens.count(), 0)
        self.assertTrue(any("caminho inseguro" in aviso for aviso in lote.avisos))

    def test_extensao_pdf_sem_assinatura_vai_para_revisao(self):
        lote = self._receber(montar_zip("Lote/Jundiaí/Lei-1-2024.pdf", b"nao e pdf"))
        resposta = self.client.post(
            reverse("api_inspecionar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 200)
        item = lote.itens.get()
        self.assertEqual(item.estado, "revisao")
        self.assertIn("assinatura do arquivo não corresponde a PDF", item.avisos)
