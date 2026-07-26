import re
from pathlib import Path


def corrigir_modelo() -> None:
    caminho = Path("applications/models.py")
    texto = caminho.read_text(encoding="utf-8")
    if 'self.arquivo.open("rb")' in texto:
        return

    padrao = re.compile(
        r"    def _calcular_sha256\(self\) -> str:\n.*?(?=\n    def _localizar_duplicado)",
        re.DOTALL,
    )
    metodo = '''    def _calcular_sha256(self) -> str:
        resumo = sha256()
        estava_fechado = self.arquivo.closed
        arquivo = None
        posicao_original = None

        try:
            if estava_fechado:
                self.arquivo.open("rb")

            arquivo = self.arquivo.file
            if arquivo.seekable():
                posicao_original = arquivo.tell()
                arquivo.seek(0)

            if hasattr(arquivo, "chunks"):
                for bloco in arquivo.chunks():
                    resumo.update(bloco)
            else:
                while bloco := arquivo.read(1024 * 1024):
                    resumo.update(bloco)

            return resumo.hexdigest()
        finally:
            if estava_fechado:
                self.arquivo.close()
            elif arquivo is not None and posicao_original is not None:
                arquivo.seek(posicao_original)
'''
    texto, quantidade = padrao.subn(metodo.rstrip(), texto, count=1)
    if quantidade != 1:
        raise RuntimeError(f"Método substituído {quantidade} vezes; esperado: 1.")
    caminho.write_text(texto, encoding="utf-8")


def corrigir_testes_resposta() -> None:
    caminho_interface = Path("applications/test_interface_qualificacao.py")
    texto_interface = caminho_interface.read_text(encoding="utf-8")
    texto_interface = texto_interface.replace("from django.db import connections\n", "")
    texto_interface = re.sub(
        r"class TestesInterfaceQualificacao\(TestCase\):\n"
        r"    @classmethod\n"
        r"    def setUpClass\(cls\):\n"
        r"        connections\.close_all\(\)\n"
        r"        super\(\)\.setUpClass\(\)\n\n",
        "class TestesInterfaceQualificacao(TestCase):\n",
        texto_interface,
        count=1,
    )
    texto_interface = texto_interface.replace(
        "        download.close()\n",
        "        download.file_to_stream.close()\n",
    )
    caminho_interface.write_text(texto_interface, encoding="utf-8")

    caminho_pdf = Path("applications/test_pdf_iframe.py")
    texto_pdf = caminho_pdf.read_text(encoding="utf-8")
    texto_pdf = texto_pdf.replace(
        "                resposta.close()\n",
        "                resposta.file_to_stream.close()\n",
    )
    caminho_pdf.write_text(texto_pdf, encoding="utf-8")


def reescrever_testes_portabilidade() -> None:
    Path("applications/test_portabilidade_arquivos.py").write_text(
        '''from hashlib import sha256
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
    CONTEUDO = b"%PDF-1.7\\nconteudo"

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
''',
        encoding="utf-8",
    )


if __name__ == "__main__":
    corrigir_modelo()
    corrigir_testes_resposta()
    reescrever_testes_portabilidade()
    Path(".github/workflows/aplicar-correcoes-portabilidade.yml").unlink(missing_ok=True)
