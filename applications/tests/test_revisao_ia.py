from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from applications.models import (
    AplicacaoMunicipal,
    ArtefatoProcessado,
    DocumentoNormativo,
    Municipio,
    ProcessamentoDocumento,
    TipoNormativo,
    VersaoDocumento,
)
from applications.revisao_ia import (
    RespostaRevisao,
    avaliar_gates,
    executar_revisao_versao,
    revisar_markdown,
    segmentar_markdown,
)


class ClienteFalso:
    def __init__(self, respostas: list[RespostaRevisao]) -> None:
        self.respostas = iter(respostas)

    def revisar(self, *, unidade: str, texto: str):
        resposta = next(self.respostas)
        return resposta, {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "duracao_segundos": 0.1,
        }


class TestesNucleoRevisao(TestCase):
    def test_segmenta_por_artigos_sem_perder_conteudo(self):
        texto = "# Lei\n\nArt. 1º Texto.\n\nArt. 2º Outro texto.\n"

        unidades = segmentar_markdown(texto, max_caracteres=1_000)

        self.assertGreaterEqual(len(unidades), 3)
        self.assertEqual("".join(unidade.texto for unidade in unidades), texto)

    def test_gate_bloqueia_alteracao_de_numero_normativo(self):
        original = "Art. 12. O coeficiente será de 2,5 e o limite de 30%."
        resposta = RespostaRevisao(
            status="correcao_estrutural_provavel",
            confianca=0.99,
            texto_proposto="Art. 13. O coeficiente será de 3,5 e o limite de 40%.",
        )

        gate = avaliar_gates(original, resposta.texto_proposto, resposta)

        self.assertFalse(gate.aprovada)
        self.assertIn("elementos_normativos_protegidos_alterados", gate.motivos)

    def test_unidade_bloqueada_preserva_original(self):
        original = "Art. 1º A taxa é 20%.\n"
        cliente = ClienteFalso(
            [
                RespostaRevisao(
                    status="trecho_ambiguo",
                    confianca=0.5,
                    texto_proposto="Art. 1º A taxa é 25%.\n",
                    exige_validacao_humana=True,
                )
            ]
        )

        revisado, registros, metricas = revisar_markdown(
            original,
            cliente,
            max_caracteres=1_000,
        )

        self.assertEqual(revisado, original)
        self.assertFalse(registros[0]["gate_aprovado"])
        self.assertEqual(metricas["unidades_bloqueadas"], 1)
        self.assertEqual(metricas["uso_ia"]["prompt_tokens"], 100)


class TesteIntegracaoRevisao(TestCase):
    def setUp(self):
        municipio = Municipio.objects.create(nome="Valinhos", uf="SP")
        aplicacao = AplicacaoMunicipal.objects.create(
            municipio=municipio,
            titulo="Aplicação piloto",
        )
        tipo = TipoNormativo.objects.get(codigo="lei_ordinaria")
        documento = DocumentoNormativo.objects.create(
            aplicacao=aplicacao,
            tipo=tipo,
            numero="7.730",
            ano=2019,
            titulo="Plano Diretor",
        )
        self.documento = documento

    def test_execucao_preserva_origem_e_grava_tres_artefatos(self):
        markdown = "Art. 1º Texto com hifeni-\nzação indevida.\n"
        resposta = RespostaRevisao(
            status="correcao_mecanica_segura",
            confianca=0.98,
            texto_proposto="Art. 1º Texto com hifenização indevida.\n",
            problemas=["hifenização de final de linha"],
        )
        cliente = ClienteFalso([resposta])

        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao = VersaoDocumento.objects.create(
                documento=self.documento,
                arquivo=SimpleUploadedFile("plano.pdf", b"pdf", "application/pdf"),
                mime_type="application/pdf",
            )
            conversao = ProcessamentoDocumento.objects.create(
                versao_documento=versao,
                etapa=ProcessamentoDocumento.Etapa.CONVERSAO,
                status=ProcessamentoDocumento.Status.CONCLUIDO,
                ferramenta="teste",
                rota_documento=ProcessamentoDocumento.RotaDocumento.TEXTO_NATIVO,
            )
            artefato_origem = ArtefatoProcessado(
                processamento=conversao,
                tipo=ArtefatoProcessado.Tipo.MARKDOWN,
                sha256="0" * 64,
                tamanho_bytes=len(markdown.encode("utf-8")),
                mime_type="text/markdown",
            )
            artefato_origem.arquivo.save(
                "convertido.md",
                ContentFile(markdown.encode("utf-8")),
                save=False,
            )
            artefato_origem.save()

            processamento = executar_revisao_versao(
                versao,
                modelo="modelo-teste",
                cliente=cliente,
                max_caracteres=1_000,
            )

            self.assertEqual(processamento.status, ProcessamentoDocumento.Status.CONCLUIDO)
            self.assertEqual(processamento.artefatos.count(), 3)
            self.assertEqual(processamento.metricas["unidades_autoaprovadas"], 1)
            artefato_origem.refresh_from_db()
            with artefato_origem.arquivo.open("rb") as stream:
                self.assertEqual(stream.read().decode("utf-8"), markdown)
            candidato = processamento.artefatos.get(tipo=ArtefatoProcessado.Tipo.MARKDOWN)
            with candidato.arquivo.open("rb") as stream:
                self.assertIn("hifenização", stream.read().decode("utf-8"))
