from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from .models import (
    AplicacaoMunicipal,
    ArtefatoProcessado,
    DiagnosticoPagina,
    DocumentoNormativo,
    Municipio,
    ProcessamentoDocumento,
    TipoNormativo,
    VersaoDocumento,
)
from .qualificacao import ErroQualificacaoDocumento, qualificar_versao


@dataclass(slots=True)
class PaginaSimulada:
    page_number: int
    route: str
    page_type: str
    has_native_text: bool
    character_count: int
    content_image_count: int = 0
    raw_image_count: int = 0
    decorative_image_count: int = 0
    suspected_table: bool = False
    suspected_map: bool = False
    native_extraction_mode: str = "layout"
    rotated_text_detected: bool = False
    warnings: list[str] = field(default_factory=list)
    layout_character_count: int = 0
    simple_character_count: int = 0
    extraction_warnings: list[str] = field(default_factory=list)
    table_assessment: object | None = None
    coordinate_assessment: object | None = None
    raster_visual_assessment: object | None = None
    ocr_quality: object | None = None
    preserved_visual_text: bool = False
    preserved_review_image: bool = False


@dataclass(slots=True)
class DiagnosticoSimulado:
    source_path: Path
    sha256: str
    page_count: int
    pages: list[PaginaSimulada]
    repeated_graphics: list[object] = field(default_factory=list)


class TestesQualificacaoDocumento(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(
            nome="Recife",
            uf="PE",
            codigo_ibge="2611606",
        )
        self.aplicacao = AplicacaoMunicipal.objects.create(
            municipio=self.municipio,
            titulo="Aplicação Recife",
        )
        self.documento = DocumentoNormativo.objects.create(
            aplicacao=self.aplicacao,
            tipo=TipoNormativo.objects.get(codigo="lei_complementar"),
            numero="2",
            ano=2021,
            titulo="Plano Diretor",
        )

    def _criar_versao(self, conteudo: bytes = b"%PDF-1.7\nconteudo") -> VersaoDocumento:
        return VersaoDocumento.objects.create(
            documento=self.documento,
            arquivo=SimpleUploadedFile("plano-diretor.pdf", conteudo, "application/pdf"),
        )

    @staticmethod
    def _motor_simulado(caminho: Path, min_native_chars: int = 40) -> DiagnosticoSimulado:
        assert min_native_chars == 40
        return DiagnosticoSimulado(
            source_path=caminho,
            sha256="hash-do-motor",
            page_count=2,
            pages=[
                PaginaSimulada(
                    page_number=1,
                    route="native",
                    page_type="text",
                    has_native_text=True,
                    character_count=1200,
                    layout_character_count=1200,
                ),
                PaginaSimulada(
                    page_number=2,
                    route="ocr",
                    page_type="unknown",
                    has_native_text=False,
                    character_count=0,
                    content_image_count=1,
                    raw_image_count=1,
                    warnings=["camada textual insuficiente"],
                ),
            ],
        )

    def test_qualificacao_persiste_paginas_metricas_e_artefato(self):
        with (
            TemporaryDirectory() as diretorio,
            self.settings(MEDIA_ROOT=Path(diretorio)),
            patch("applications.qualificacao._carregar_motor", return_value=self._motor_simulado),
            patch("applications.qualificacao._versao_ferramenta", return_value="0.7.3"),
        ):
            versao = self._criar_versao()
            processamento = qualificar_versao(versao)

            self.assertEqual(processamento.status, ProcessamentoDocumento.Status.CONCLUIDO)
            self.assertEqual(processamento.rota_documento, ProcessamentoDocumento.RotaDocumento.MISTO)
            self.assertEqual(processamento.metricas["paginas_total"], 2)
            self.assertEqual(DiagnosticoPagina.objects.filter(processamento=processamento).count(), 2)
            artefato = ArtefatoProcessado.objects.get(processamento=processamento)
            self.assertTrue(artefato.arquivo.storage.exists(artefato.arquivo.name))
            self.assertEqual(artefato.mime_type, "application/json")

            versao.refresh_from_db()
            self.documento.refresh_from_db()
            self.assertEqual(versao.mime_type, "application/pdf")
            self.assertEqual(self.documento.status, DocumentoNormativo.Status.VERIFICADO)

    def test_qualificacao_reutiliza_execucao_concluida(self):
        with (
            TemporaryDirectory() as diretorio,
            self.settings(MEDIA_ROOT=Path(diretorio)),
            patch("applications.qualificacao._carregar_motor", return_value=self._motor_simulado),
            patch("applications.qualificacao._versao_ferramenta", return_value="0.7.3"),
        ):
            versao = self._criar_versao()
            primeira = qualificar_versao(versao)
            segunda = qualificar_versao(versao)

            self.assertEqual(primeira.pk, segunda.pk)
            self.assertEqual(versao.processamentos.count(), 1)

    def test_arquivo_sem_assinatura_pdf_vai_para_quarentena(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao = self._criar_versao(b"nao e um pdf")

            with self.assertRaises(ErroQualificacaoDocumento):
                qualificar_versao(versao)

            processamento = versao.processamentos.get()
            self.documento.refresh_from_db()
            self.assertEqual(processamento.status, ProcessamentoDocumento.Status.FALHOU)
            self.assertEqual(
                processamento.rota_documento,
                ProcessamentoDocumento.RotaDocumento.MANUAL,
            )
            self.assertEqual(self.documento.status, DocumentoNormativo.Status.QUARENTENA)

    def test_comando_qualifica_versao_especifica(self):
        with (
            TemporaryDirectory() as diretorio,
            self.settings(MEDIA_ROOT=Path(diretorio)),
            patch("applications.qualificacao._carregar_motor", return_value=self._motor_simulado),
            patch("applications.qualificacao._versao_ferramenta", return_value="0.7.3"),
        ):
            versao = self._criar_versao()
            saida = StringIO()

            call_command("qualificar_documentos", versao=versao.pk, stdout=saida)

            self.assertIn("Qualificação encerrada", saida.getvalue())
            self.assertEqual(
                versao.processamentos.get().status,
                ProcessamentoDocumento.Status.CONCLUIDO,
            )
