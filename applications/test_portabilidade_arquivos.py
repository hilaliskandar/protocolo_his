from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from applications.models import (
    AplicacaoMunicipal,
    DocumentoNormativo,
    Municipio,
    TipoNormativo,
    VersaoDocumento,
)


class TestesPortabilidadeArquivos(TestCase):
    def test_calculo_sha256_fecha_handle_aberto_internamente(self):
        municipio = Municipio.objects.create(nome="Recife", uf="PE")
        aplicacao = AplicacaoMunicipal.objects.create(
            municipio=municipio,
            titulo="Aplicação Recife",
        )
        documento = DocumentoNormativo.objects.create(
            aplicacao=aplicacao,
            tipo=TipoNormativo.objects.get(codigo="lei_complementar"),
            numero="2",
            ano=2021,
            titulo="Plano Diretor",
        )

        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            criada = VersaoDocumento.objects.create(
                documento=documento,
                arquivo=SimpleUploadedFile(
                    "hash-pendente.pdf",
                    b"%PDF-1.7\nconteudo",
                    "application/pdf",
                ),
                mime_type="application/pdf",
            )
            versao = VersaoDocumento.objects.get(pk=criada.pk)

            self.assertTrue(versao.arquivo.closed)
            resumo = versao._calcular_sha256()

            self.assertEqual(resumo, criada.sha256)
            self.assertTrue(versao.arquivo.closed)
