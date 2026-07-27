from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from applications.models import (
    AnexoNormativo,
    AplicacaoMunicipal,
    ArtefatoProcessado,
    ArtigoNormativo,
    AtoNormativo,
    DocumentoNormativo,
    Municipio,
    OcorrenciaDocumental,
    ProcessamentoDocumento,
    TipoNormativo,
    VersaoDocumento,
)
from applications.segmentacao import ErroSegmentacao, executar_segmentacao, segmentar_markdown


MARKDOWN_EXEMPLO = """# LEI COMPLEMENTAR Nº 10/2024

Dispõe sobre regras urbanísticas.

<!-- page: 1 -->
## Art. 1º
Esta lei estabelece as regras gerais.

Artigo 2° O licenciamento observará os parâmetros definidos.

<!-- page: 2 -->
**Art. 4-A** O Município poderá regulamentar este dispositivo.

## ANEXO I — QUADRO DE PARÂMETROS
Conteúdo tabular do anexo.
"""


class BaseSegmentacaoTeste(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Município Segmentação", uf="SP")
        self.aplicacao = AplicacaoMunicipal.objects.create(
            municipio=self.municipio,
            titulo="Aplicação de segmentação",
        )
        self.tipo = TipoNormativo.objects.create(
            codigo="lei_segmentacao",
            nome="Lei de segmentação",
            sigla="LS",
            esfera=TipoNormativo.Esfera.MUNICIPAL,
            fonte_normativa="https://example.test/segmentacao",
            dispositivo_fonte="Teste automatizado",
        )
        self.documento = DocumentoNormativo.objects.create(
            aplicacao=self.aplicacao,
            tipo=self.tipo,
            numero="10",
            ano=2024,
            titulo="Lei de segmentação",
        )

    def criar_versao_com_markdown(self, markdown: str = MARKDOWN_EXEMPLO):
        versao = VersaoDocumento.objects.create(
            documento=self.documento,
            versao=1,
            arquivo=SimpleUploadedFile("lei.pdf", b"%PDF-1.4\nsegmentacao", "application/pdf"),
            mime_type="application/pdf",
        )
        processamento = ProcessamentoDocumento.objects.create(
            versao_documento=versao,
            etapa=ProcessamentoDocumento.Etapa.CONVERSAO,
            status=ProcessamentoDocumento.Status.CONCLUIDO,
            rota_documento=ProcessamentoDocumento.RotaDocumento.TEXTO_NATIVO,
            ferramenta="teste-conversao",
            versao_ferramenta="1",
            versao_codigo="teste",
        )
        conteudo = markdown.encode("utf-8")
        artefato = ArtefatoProcessado.objects.create(
            processamento=processamento,
            tipo=ArtefatoProcessado.Tipo.MARKDOWN,
            arquivo=SimpleUploadedFile("lei.md", conteudo, "text/markdown"),
            sha256=sha256(conteudo).hexdigest(),
            tamanho_bytes=len(conteudo),
            mime_type="text/markdown",
        )
        return versao, artefato


class TesteParserSegmentacao(BaseSegmentacaoTeste):
    def test_reconhece_variantes_artigos_lacuna_e_anexo(self):
        resultado = segmentar_markdown(MARKDOWN_EXEMPLO)

        self.assertEqual(len(resultado.artigos), 3)
        self.assertEqual(resultado.artigos[0].numero_normalizado, 1)
        self.assertEqual(resultado.artigos[1].numero_normalizado, 2)
        self.assertEqual(resultado.artigos[2].numero_normalizado, 4)
        self.assertEqual(resultado.artigos[2].sufixo, "A")
        self.assertEqual(resultado.artigos[2].pagina_inicial, 2)
        self.assertEqual(len(resultado.anexos), 1)
        self.assertEqual(resultado.anexos[0].tipo, AnexoNormativo.Tipo.TEXTO)
        self.assertEqual(resultado.metricas["lacunas_sequencia"], 1)
        self.assertTrue(resultado.metricas["gate_cobertura_98"])

    def test_duplicacao_mantem_evidencias_integrais(self):
        markdown = """Art. 1º Primeiro texto.\n\nArt. 1º Segundo texto, preservado na evidência.\n"""
        resultado = segmentar_markdown(markdown)

        self.assertEqual(resultado.metricas["duplicacoes_numeracao"], 1)
        ocorrencia = next(
            item
            for item in resultado.ocorrencias
            if item.categoria == "segmentacao_artigo_duplicado"
        )
        self.assertEqual(len(ocorrencia.evidencias), 2)
        self.assertIn("Segundo texto", ocorrencia.evidencias[1]["texto"])
        self.assertEqual(
            resultado.artigos[0].status_sequencia,
            ArtigoNormativo.StatusSequencia.DUPLICADO,
        )

    def test_markdown_sem_artigo_produz_ocorrencia_critica(self):
        resultado = segmentar_markdown("# Ementa\nTexto sem cabeçalho normativo.")
        ocorrencia = resultado.ocorrencias[0]
        self.assertEqual(ocorrencia.categoria, "segmentacao_sem_artigos")
        self.assertEqual(ocorrencia.severidade, OcorrenciaDocumental.Severidade.CRITICA)


class TestePersistenciaSegmentacao(BaseSegmentacaoTeste):
    def test_simulacao_nao_persiste_registros(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao, _ = self.criar_versao_com_markdown()
            resultado, processamento, reutilizado = executar_segmentacao(versao)

            self.assertEqual(resultado.metricas["artigos_detectados"], 3)
            self.assertIsNone(processamento)
            self.assertFalse(reutilizado)
            self.assertFalse(AtoNormativo.objects.exists())

    def test_confirmacao_persiste_e_segunda_execucao_reutiliza(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao, _ = self.criar_versao_com_markdown()
            _, primeiro, reutilizado = executar_segmentacao(versao, confirmar=True)
            _, segundo, reutilizado_segunda = executar_segmentacao(versao, confirmar=True)

            self.assertIsNotNone(primeiro)
            self.assertFalse(reutilizado)
            self.assertEqual(primeiro.pk, segundo.pk)
            self.assertTrue(reutilizado_segunda)
            self.assertEqual(AtoNormativo.objects.count(), 1)
            self.assertEqual(ArtigoNormativo.objects.count(), 3)
            self.assertEqual(AnexoNormativo.objects.count(), 1)
            self.assertEqual(
                ProcessamentoDocumento.objects.filter(ferramenta="segmentador-normativo").count(),
                1,
            )
            self.assertTrue(
                ArtefatoProcessado.objects.filter(
                    processamento=primeiro,
                    tipo=ArtefatoProcessado.Tipo.DIAGNOSTICO_JSON,
                ).exists()
            )

    def test_duplicado_persiste_um_artigo_e_ocorrencia_com_evidencias(self):
        markdown = "Art. 1º Primeiro.\n\nArt. 1º Segundo.\n"
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao, _ = self.criar_versao_com_markdown(markdown)
            executar_segmentacao(versao, confirmar=True)

            self.assertEqual(ArtigoNormativo.objects.count(), 1)
            artigo = ArtigoNormativo.objects.get()
            self.assertEqual(artigo.status_sequencia, ArtigoNormativo.StatusSequencia.DUPLICADO)
            ocorrencia = OcorrenciaDocumental.objects.get(
                categoria="segmentacao_artigo_duplicado"
            )
            self.assertEqual(len(ocorrencia.evidencias), 2)

    def test_forcar_nao_substitui_revisao_humana_sem_autorizacao(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao, _ = self.criar_versao_com_markdown()
            executar_segmentacao(versao, confirmar=True)
            artigo = ArtigoNormativo.objects.order_by("pk").first()
            artigo.status_auditoria = ArtigoNormativo.StatusAuditoria.REVISADO
            artigo.save(update_fields=["status_auditoria", "atualizado_em"])

            with self.assertRaises(ErroSegmentacao):
                executar_segmentacao(versao, confirmar=True, forcar=True)

            self.assertEqual(ArtigoNormativo.objects.filter(pk=artigo.pk).count(), 1)

    def test_modelos_existentes_continuam_validos(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao, _ = self.criar_versao_com_markdown()
            executar_segmentacao(versao, confirmar=True)
            for artigo in ArtigoNormativo.objects.all():
                artigo.full_clean()
            for ato in AtoNormativo.objects.all():
                ato.full_clean()
            for anexo in AnexoNormativo.objects.all():
                anexo.full_clean()

        with self.assertRaises(ValidationError):
            ArtigoNormativo(numero_textual="").full_clean()
