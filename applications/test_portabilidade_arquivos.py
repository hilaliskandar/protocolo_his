from hashlib import sha256
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
    CONTEUDO = b"%PDF-1.7\nconteudo"

    def setUp(self):
        municipio = Municipio.objects.create(nome="Recife", uf="PE")
        aplicacao = AplicacaoMunicipal.objects.create(
            municipio=municipio,
            titulo="Aplicação Recife",
        )
        self.documento = DocumentoNormativo.objects.create(
            aplicacao=aplicacao,
            tipo=TipoNormativo.objects.get(codigo="lei_complementar"),
            numero="2",
            ano=2021,
            titulo="Plano Diretor",
        )
        self.resumo_esperado = sha256(self.CONTEUDO).hexdigest()

    def _criar_versao(self):
        criada = VersaoDocumento.objects.create(
            documento=self.documento,
            arquivo=SimpleUploadedFile(
                "hash-pendente.pdf",
                self.CONTEUDO,
                "application/pdf",
            ),
            mime_type="application/pdf",
        )
        return criada, VersaoDocumento.objects.get(pk=criada.pk)

    def test_calculo_sha256_fecha_handle_aberto_internamente(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            criada, versao = self._criar_versao()
            try:
                self.assertTrue(versao.arquivo.closed)
                resumo = versao._calcular_sha256()
                self.assertEqual(resumo, self.resumo_esperado)
                self.assertEqual(resumo, criada.sha256)
                self.assertTrue(versao.arquivo.closed)
            finally:
                criada.arquivo.close()
                versao.arquivo.close()

    def test_calculo_sha256_pode_ser_executado_duas_vezes(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            criada, versao = self._criar_versao()
            try:
                primeiro = versao._calcular_sha256()
                segundo = versao._calcular_sha256()
                self.assertEqual(primeiro, self.resumo_esperado)
                self.assertEqual(segundo, self.resumo_esperado)
                self.assertTrue(versao.arquivo.closed)
            finally:
                criada.arquivo.close()
                versao.arquivo.close()

    def test_calculo_sha256_preserva_handle_aberto_e_posicao(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            criada, versao = self._criar_versao()
            try:
                versao.arquivo.open("rb")
                versao.arquivo.seek(5)
                resumo = versao._calcular_sha256()
                self.assertEqual(resumo, self.resumo_esperado)
                self.assertFalse(versao.arquivo.closed)
                self.assertEqual(versao.arquivo.tell(), 5)
            finally:
                criada.arquivo.close()
                versao.arquivo.close()
