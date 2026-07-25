from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import (
    AplicacaoMunicipal,
    ArtefatoProcessado,
    DocumentoNormativo,
    Municipio,
    ProcessamentoDocumento,
    TipoNormativo,
    VersaoDocumento,
)


class TestesVisualizadorDocumental(TestCase):
    def setUp(self):
        self._diretorio = TemporaryDirectory()
        self.addCleanup(self._diretorio.cleanup)
        self._settings = self.settings(MEDIA_ROOT=Path(self._diretorio.name))
        self._settings.enable()
        self.addCleanup(self._settings.disable)

        municipio = Municipio.objects.create(
            nome="Recife",
            uf="PE",
            codigo_ibge="2611606",
        )
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
            status=DocumentoNormativo.Status.VERIFICADO,
        )
        self.versao = VersaoDocumento.objects.create(
            documento=self.documento,
            arquivo=SimpleUploadedFile(
                "plano-diretor.pdf",
                b"%PDF-1.7\nconteudo de teste",
                "application/pdf",
            ),
            mime_type="application/pdf",
        )
        self.processamento = ProcessamentoDocumento.objects.create(
            versao_documento=self.versao,
            etapa=ProcessamentoDocumento.Etapa.CONVERSAO,
            status=ProcessamentoDocumento.Status.CONCLUIDO,
            ferramenta="conversor-his",
            versao_ferramenta="0.7.3",
        )

    def _criar_markdown(self, conteudo: str) -> ArtefatoProcessado:
        dados = conteudo.encode("utf-8")
        artefato = ArtefatoProcessado(
            processamento=self.processamento,
            tipo=ArtefatoProcessado.Tipo.MARKDOWN,
            sha256=sha256(dados).hexdigest(),
            tamanho_bytes=len(dados),
            mime_type="text/markdown",
        )
        artefato.arquivo.save("plano-diretor.md", ContentFile(dados), save=False)
        artefato.save()
        return artefato

    def test_leitor_exibe_pdf_e_estado_sem_markdown(self):
        resposta = self.client.get(reverse("leitor_documento", args=[self.documento.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "PDF original")
        self.assertContains(resposta, "Aguardando conversão")
        self.assertContains(resposta, reverse("exibir_pdf", args=[self.versao.pk]))

    def test_pdf_e_servido_inline_com_tipo_correto(self):
        resposta = self.client.get(reverse("exibir_pdf", args=[self.versao.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.headers["Content-Type"], "application/pdf")
        self.assertIn("inline", resposta.headers["Content-Disposition"])
        self.assertEqual(resposta.headers["X-Content-Type-Options"], "nosniff")
        resposta.close()

    def test_markdown_e_renderizado_sem_executar_html(self):
        self._criar_markdown("# TÍTULO I\n\nArt. 1º Texto.\n\n<script>alert('x')</script>")

        resposta = self.client.get(
            reverse("leitor_documento", args=[self.documento.pk]),
            {"modo": "markdown"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "<h1>TÍTULO I</h1>", html=True)
        self.assertContains(resposta, "Art. 1º Texto.")
        self.assertNotContains(resposta, "<script>alert('x')</script>", html=False)
        self.assertContains(resposta, "&lt;script&gt;alert('x')&lt;/script&gt;", html=False)

    def test_comparacao_exibe_pdf_e_markdown(self):
        self._criar_markdown("# Plano Diretor\n\nConteúdo convertido.")

        resposta = self.client.get(
            reverse("leitor_documento", args=[self.documento.pk]),
            {"modo": "comparacao"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "PDF original")
        self.assertContains(resposta, "Markdown convertido")
        self.assertContains(resposta, "Conteúdo convertido.")

    def test_modo_invalido_retorna_ao_pdf(self):
        resposta = self.client.get(
            reverse("leitor_documento", args=[self.documento.pk]),
            {"modo": "inexistente"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["modo"], "pdf")
