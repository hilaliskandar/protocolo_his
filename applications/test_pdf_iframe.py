from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from applications.models import (
    AplicacaoMunicipal,
    DocumentoNormativo,
    Municipio,
    TipoNormativo,
    VersaoDocumento,
)


class TesteExibicaoPdfNoLeitor(TestCase):
    def test_pdf_permite_iframe_da_mesma_origem(self):
        municipio = Municipio.objects.create(nome="Recife", uf="PE")
        aplicacao = AplicacaoMunicipal.objects.create(
            municipio=municipio,
            titulo="Aplicação Recife",
        )
        tipo = TipoNormativo.objects.get(codigo="lei_complementar")
        documento = DocumentoNormativo.objects.create(
            aplicacao=aplicacao,
            tipo=tipo,
            numero="2",
            ano=2021,
            titulo="Lei complementar nº 2/2021",
        )

        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao = VersaoDocumento.objects.create(
                documento=documento,
                arquivo=SimpleUploadedFile(
                    "lei-complementar.pdf",
                    b"%PDF-1.4\n% arquivo de teste\n",
                    "application/pdf",
                ),
                mime_type="application/pdf",
            )

            resposta = self.client.get(reverse("exibir_pdf", args=[versao.pk]))

            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta["Content-Type"], "application/pdf")
            self.assertEqual(resposta["X-Frame-Options"], "SAMEORIGIN")
            self.assertTrue(resposta["Content-Disposition"].startswith("inline;"))
