from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from applications.models import (
    AplicacaoMunicipal,
    ArtefatoProcessado,
    DocumentoNormativo,
    Municipio,
    ProcessamentoDocumento,
    TipoNormativo,
    VersaoDocumento,
)


class TesteLeitorComMultiplasVersoes(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Jundiaí", uf="SP")
        self.aplicacao = AplicacaoMunicipal.objects.create(
            municipio=self.municipio,
            titulo="Aplicação Jundiaí",
        )
        self.tipo = TipoNormativo.objects.get(codigo="lei_complementar")
        self.documento = DocumentoNormativo.objects.create(
            aplicacao=self.aplicacao,
            tipo=self.tipo,
            numero="606",
            ano=2021,
            titulo="Código de Obras e Edificações",
        )

    def _criar_versao_com_markdown(
        self,
        *,
        numero_versao: int,
        nome_pdf: str,
        conteudo_markdown: str,
    ) -> tuple[VersaoDocumento, ArtefatoProcessado]:
        versao = VersaoDocumento.objects.create(
            documento=self.documento,
            versao=numero_versao,
            arquivo=SimpleUploadedFile(
                nome_pdf,
                f"%PDF-1.4\nversao {numero_versao}\n".encode(),
                "application/pdf",
            ),
            mime_type="application/pdf",
        )
        processamento = ProcessamentoDocumento.objects.create(
            versao_documento=versao,
            etapa=ProcessamentoDocumento.Etapa.CONVERSAO,
            status=ProcessamentoDocumento.Status.CONCLUIDO,
            ferramenta="teste",
            versao_ferramenta="1",
        )
        artefato = ArtefatoProcessado(
            processamento=processamento,
            tipo=ArtefatoProcessado.Tipo.MARKDOWN,
            mime_type="text/markdown",
        )
        artefato.arquivo.save(
            f"versao-{numero_versao}.md",
            ContentFile(conteudo_markdown.encode("utf-8")),
            save=True,
        )
        return versao, artefato

    def test_selecao_explicitamente_vincula_pdf_e_markdown_a_mesma_versao(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao_1, artefato_1 = self._criar_versao_com_markdown(
                numero_versao=1,
                nome_pdf="consolidacao-2023.pdf",
                conteudo_markdown="# VERSAO ANTIGA\n",
            )
            versao_2, artefato_2 = self._criar_versao_com_markdown(
                numero_versao=2,
                nome_pdf="consolidacao-2024.pdf",
                conteudo_markdown="# VERSAO NOVA\n",
            )

            resposta = self.client.get(
                reverse("leitor_documento", args=[self.documento.pk]),
                {"modo": "comparacao", "versao": versao_1.pk},
            )

            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta.context["versao"], versao_1)
            self.assertEqual(resposta.context["artefato_markdown"], artefato_1)
            self.assertNotEqual(resposta.context["artefato_markdown"], artefato_2)
            self.assertContains(resposta, "VERSAO ANTIGA")
            self.assertNotContains(resposta, "VERSAO NOVA")
            self.assertContains(resposta, reverse("exibir_pdf", args=[versao_1.pk]))
            self.assertNotContains(resposta, reverse("exibir_pdf", args=[versao_2.pk]))

    def test_sem_parametro_abre_a_versao_documental_mais_recente(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            self._criar_versao_com_markdown(
                numero_versao=1,
                nome_pdf="consolidacao-2023.pdf",
                conteudo_markdown="# VERSAO ANTIGA\n",
            )
            versao_2, artefato_2 = self._criar_versao_com_markdown(
                numero_versao=2,
                nome_pdf="consolidacao-2024.pdf",
                conteudo_markdown="# VERSAO NOVA\n",
            )

            resposta = self.client.get(
                reverse("leitor_documento", args=[self.documento.pk]),
                {"modo": "comparacao"},
            )

            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta.context["versao"], versao_2)
            self.assertEqual(resposta.context["artefato_markdown"], artefato_2)
            self.assertContains(resposta, "VERSAO NOVA")

    def test_rejeita_versao_pertencente_a_outro_documento(self):
        outro_documento = DocumentoNormativo.objects.create(
            aplicacao=self.aplicacao,
            tipo=self.tipo,
            numero="607",
            ano=2021,
            titulo="Outro ato",
        )

        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao_estranha = VersaoDocumento.objects.create(
                documento=outro_documento,
                arquivo=SimpleUploadedFile(
                    "outro.pdf",
                    b"%PDF-1.4\noutro documento\n",
                    "application/pdf",
                ),
                mime_type="application/pdf",
            )

            resposta = self.client.get(
                reverse("leitor_documento", args=[self.documento.pk]),
                {"versao": versao_estranha.pk},
            )

            self.assertEqual(resposta.status_code, 404)
