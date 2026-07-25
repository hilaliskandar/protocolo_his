from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .conversao import ErroConversaoDocumento, converter_versao
from .models import (
    AplicacaoMunicipal,
    ArtefatoProcessado,
    DocumentoNormativo,
    Municipio,
    ProcessamentoDocumento,
    TipoNormativo,
    VersaoDocumento,
)


class TestesConversaoDocumental(TestCase):
    def setUp(self):
        self._diretorio = TemporaryDirectory()
        self.addCleanup(self._diretorio.cleanup)
        self._settings = self.settings(MEDIA_ROOT=Path(self._diretorio.name))
        self._settings.enable()
        self.addCleanup(self._settings.disable)

        municipio = Municipio.objects.create(nome="Recife", uf="PE", codigo_ibge="2611606")
        aplicacao = AplicacaoMunicipal.objects.create(municipio=municipio, titulo="Recife")
        tipo = TipoNormativo.objects.get(codigo="lei_complementar")
        self.documento = DocumentoNormativo.objects.create(
            aplicacao=aplicacao,
            tipo=tipo,
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
        self.qualificacao = ProcessamentoDocumento.objects.create(
            versao_documento=self.versao,
            etapa=ProcessamentoDocumento.Etapa.QUALIFICACAO,
            status=ProcessamentoDocumento.Status.CONCLUIDO,
            rota_documento=ProcessamentoDocumento.RotaDocumento.MISTO,
            ferramenta="conversor-his",
            versao_ferramenta="0.7.3",
            versao_codigo="abc",
            parametros={"min_native_chars": 40},
        )

    def _motor_falso(self, caminho: Path, saida: Path, *, dpi: int, source_reference: str):
        del caminho, source_reference
        analise = saida / "analise"
        ativos = saida / "ativos" / "plano-diretor"
        analise.mkdir(parents=True)
        ativos.mkdir(parents=True)
        markdown = analise / "plano-diretor.md"
        conteudo = b"# Plano Diretor\n\n## Pagina 1\n\nArt. 1o Texto convertido.\n"
        markdown.write_bytes(conteudo)
        (analise / "plano-diretor.ocr_tokens.jsonl").write_text(
            '{"page_number": 1, "text": "Art."}\n',
            encoding="utf-8",
        )
        (analise / "plano-diretor.estrutura_ocr.jsonl").write_text(
            '{"page_number": 1, "lines": []}\n',
            encoding="utf-8",
        )
        (ativos / "pagina_0001.png").write_bytes(b"PNG")
        manifesto = {
            "source_sha256": self.versao.sha256,
            "page_count": 1,
            "markdown_sha256": sha256(conteudo).hexdigest(),
            "markdown_size_bytes": len(conteudo),
            "asset_paths": [str(ativos / "pagina_0001.png")],
            "used_ocr_pages": [1],
            "review_pages": [1],
            "table_pages": [],
            "processing_seconds": 0.2,
            "dpi": dpi,
        }
        (analise / "plano-diretor.manifest.json").write_text(
            json.dumps(manifesto),
            encoding="utf-8",
        )
        return markdown

    def test_conversao_registra_markdown_pacote_e_metricas(self):
        with patch("applications.conversao._carregar_motor", return_value=self._motor_falso):
            processamento = converter_versao(self.versao)

        self.assertEqual(processamento.status, ProcessamentoDocumento.Status.CONCLUIDO)
        self.assertEqual(processamento.rota_documento, self.qualificacao.rota_documento)
        self.assertEqual(processamento.metricas["paginas_total"], 1)
        self.assertEqual(processamento.metricas["total_review_pages"], 1)
        self.assertEqual(processamento.artefatos.count(), 2)
        self.assertTrue(
            processamento.artefatos.filter(tipo=ArtefatoProcessado.Tipo.MARKDOWN).exists()
        )
        self.assertTrue(
            processamento.artefatos.filter(
                tipo=ArtefatoProcessado.Tipo.OUTRO,
                mime_type="application/zip",
            ).exists()
        )

        leitor = self.client.get(
            reverse("leitor_documento", args=[self.documento.pk]),
            {"modo": "markdown"},
        )
        self.assertContains(leitor, "Texto convertido")

    def test_conversao_concluida_e_reutilizada(self):
        with patch("applications.conversao._carregar_motor", return_value=self._motor_falso):
            primeiro = converter_versao(self.versao)
            segundo = converter_versao(self.versao)

        self.assertEqual(primeiro.pk, segundo.pk)
        self.assertEqual(
            self.versao.processamentos.filter(
                etapa=ProcessamentoDocumento.Etapa.CONVERSAO
            ).count(),
            1,
        )

    def test_conversao_exige_qualificacao_concluida(self):
        self.qualificacao.delete()

        with self.assertRaisesMessage(
            ErroConversaoDocumento,
            "qualificação concluída",
        ):
            converter_versao(self.versao)

    def test_comando_converte_uma_versao(self):
        with patch("applications.conversao._carregar_motor", return_value=self._motor_falso):
            call_command("converter_documentos", versao=self.versao.pk, dpi=300)

        self.assertTrue(
            self.versao.processamentos.filter(
                etapa=ProcessamentoDocumento.Etapa.CONVERSAO,
                status=ProcessamentoDocumento.Status.CONCLUIDO,
            ).exists()
        )
