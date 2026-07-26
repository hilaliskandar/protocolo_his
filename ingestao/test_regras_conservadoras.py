from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from .api import _item_json
from .enriquecimento import (
    DiagnosticoPreliminar,
    _metadados_do_texto,
    diagnosticar_pdf,
    normalizar_numero,
)
from .models import ImportacaoLote, ItemImportacaoLote
from .services import _aplicar_diagnostico, _classificar, _vincular_documentos_apoio


class PaginaSimulada:
    def __init__(self, texto: str):
        self.texto = texto

    def extract_text(self) -> str:
        return self.texto


class LeitorSimulado:
    def __init__(self, *textos: str):
        self.pages = [PaginaSimulada(texto) for texto in textos]


class TestesEnriquecimentoPreliminar(SimpleTestCase):
    def test_normaliza_numero_sem_perder_valor_de_exibicao(self):
        self.assertEqual(normalizar_numero("2.405"), "2405")
        self.assertEqual(normalizar_numero("9-844"), "9844")

    def test_extrai_numero_e_ano_separados_no_formato_barra(self):
        numero, ano = _metadados_do_texto("LEI COMPLEMENTAR Nº 201/2020")

        self.assertEqual(numero, "201")
        self.assertEqual(ano, 2020)

    @patch("ingestao.enriquecimento.PdfReader")
    def test_documento_com_texto_suficiente_recebe_rota_texto_nativo(self, pdf_reader):
        pdf_reader.return_value = LeitorSimulado(
            "LEI Nº 9.321/2019 " + ("conteúdo normativo " * 20)
        )

        diagnostico = diagnosticar_pdf("documento.pdf")

        self.assertEqual(diagnostico.rota_sugerida, "texto_nativo")
        self.assertEqual(diagnostico.numero_texto, "9.321")
        self.assertEqual(diagnostico.ano_texto, 2019)

    @patch("ingestao.enriquecimento.PdfReader")
    def test_documento_sem_texto_recebe_rota_ocr(self, pdf_reader):
        pdf_reader.return_value = LeitorSimulado("")

        diagnostico = diagnosticar_pdf("imagem.pdf")

        self.assertEqual(diagnostico.rota_sugerida, "ocr")
        self.assertEqual(diagnostico.caracteres_amostra, 0)
        self.assertTrue(any("OCR" in aviso for aviso in diagnostico.avisos))

    @patch("ingestao.enriquecimento.PdfReader", side_effect=ValueError("PDF inválido"))
    def test_documento_malformado_recebe_rota_manual(self, _pdf_reader):
        diagnostico = diagnosticar_pdf("corrompido.pdf")

        self.assertEqual(diagnostico.rota_sugerida, "manual")
        self.assertEqual(diagnostico.paginas, 0)
        self.assertTrue(any("PDF inválido" in aviso for aviso in diagnostico.avisos))

    def test_sugestao_textual_nao_preenche_metadado_aceito_nem_promove_item(self):
        dados = _classificar("Jarinu/Lei Ordinaria.pdf", "SP")
        diagnostico = DiagnosticoPreliminar(
            paginas=4,
            paginas_amostradas=3,
            caracteres_amostra=900,
            rota_sugerida="texto_nativo",
            texto_amostra="Lei Ordinária nº 2.076/2021",
            numero_texto="2.076",
            ano_texto=2021,
            avisos=[],
        )

        with patch("ingestao.services.diagnosticar_pdf", return_value=diagnostico):
            _aplicar_diagnostico(dados, "documento.pdf")

        self.assertEqual(dados["numero_candidato"], "")
        self.assertIsNone(dados["ano_candidato"])
        self.assertEqual(dados["numero_sugerido_texto"], "2.076")
        self.assertEqual(dados["numero_sugerido_normalizado"], "2076")
        self.assertEqual(dados["ano_sugerido_texto"], 2021)
        self.assertEqual(dados["estado"], ItemImportacaoLote.Estado.REVISAO)

    def test_referencia_interna_divergente_rebaixa_item_para_revisao(self):
        dados = _classificar("Jundiaí/lei-9321-2019.pdf", "SP")
        self.assertEqual(dados["estado"], ItemImportacaoLote.Estado.PRONTO)
        diagnostico = DiagnosticoPreliminar(
            paginas=10,
            paginas_amostradas=3,
            caracteres_amostra=1200,
            rota_sugerida="texto_nativo",
            texto_amostra="Altera a Lei nº 9.806/2022",
            numero_texto="9.806",
            ano_texto=2022,
            avisos=[],
        )

        with patch("ingestao.services.diagnosticar_pdf", return_value=diagnostico):
            _aplicar_diagnostico(dados, "documento.pdf")

        self.assertEqual(dados["numero_candidato"], "9321")
        self.assertEqual(dados["ano_candidato"], 2019)
        self.assertEqual(dados["estado"], ItemImportacaoLote.Estado.REVISAO)
        self.assertEqual(len(dados["divergencias_metadados"]), 2)
        campos = {item["campo"] for item in dados["divergencias_metadados"]}
        self.assertEqual(campos, {"numero_candidato", "ano_candidato"})

    def test_numero_equivalente_nao_gera_divergencia(self):
        dados = _classificar("Jundiaí/lei-2.405-1980.pdf", "SP")
        diagnostico = DiagnosticoPreliminar(
            paginas=2,
            paginas_amostradas=2,
            caracteres_amostra=600,
            rota_sugerida="texto_nativo",
            texto_amostra="Lei nº 2405/1980",
            numero_texto="2405",
            ano_texto=1980,
            avisos=[],
        )

        with patch("ingestao.services.diagnosticar_pdf", return_value=diagnostico):
            _aplicar_diagnostico(dados, "documento.pdf")

        self.assertEqual(dados["numero_normalizado"], "2405")
        self.assertEqual(dados["divergencias_metadados"], [])
        self.assertEqual(dados["estado"], ItemImportacaoLote.Estado.PRONTO)


class TestesPersistenciaConservadora(TestCase):
    def setUp(self):
        self.diretorio = TemporaryDirectory()
        self.addCleanup(self.diretorio.cleanup)
        self.configuracao = override_settings(MEDIA_ROOT=Path(self.diretorio.name))
        self.configuracao.enable()
        self.addCleanup(self.configuracao.disable)
        self.lote = self._criar_lote("Lote principal")

    @staticmethod
    def _arquivo_zip() -> SimpleUploadedFile:
        return SimpleUploadedFile("lote.zip", b"PK\x03\x04conteudo", "application/zip")

    def _criar_lote(self, titulo: str) -> ImportacaoLote:
        return ImportacaoLote.objects.create(
            titulo=titulo,
            origem_recebimento="Teste automatizado",
            uf_padrao="SP",
            arquivo_zip=self._arquivo_zip(),
        )

    def _criar_item(self, indice: int, **campos) -> ItemImportacaoLote:
        padrao = {
            "lote": self.lote,
            "indice_arquivo": indice,
            "caminho_relativo": f"Jundiaí/item-{indice}.pdf",
            "nome_original": f"item-{indice}.pdf",
            "municipio_candidato": "Jundiaí",
            "uf": "SP",
            "sha256": f"{indice:064x}",
            "tamanho_bytes": 100,
            "assinatura_pdf_valida": True,
            "estado": ItemImportacaoLote.Estado.REVISAO,
        }
        padrao.update(campos)
        return ItemImportacaoLote.objects.create(**padrao)

    def test_modelo_normaliza_separadamente_candidato_e_sugestao(self):
        item = self._criar_item(
            1,
            numero_candidato="2.405",
            numero_sugerido_texto="9-844",
        )

        self.assertEqual(item.numero_normalizado, "2405")
        self.assertEqual(item.numero_sugerido_normalizado, "9844")

    def test_anexo_recebe_apenas_vinculo_sugerido(self):
        principal = self._criar_item(
            1,
            natureza=ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL,
            numero_candidato="9321",
            ano_candidato=2019,
        )
        apoio = self._criar_item(
            2,
            natureza=ItemImportacaoLote.Natureza.ANEXO_NORMATIVO,
            numero_candidato="9.321",
            ano_candidato=2019,
        )

        _vincular_documentos_apoio(self.lote)
        apoio.refresh_from_db()

        self.assertEqual(apoio.documento_principal_sugerido, principal)
        self.assertIsNone(apoio.documento_principal_candidato)

    def test_sugestao_textual_isolada_nao_cria_vinculo_automatico(self):
        self._criar_item(
            1,
            natureza=ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL,
            numero_candidato="9321",
            ano_candidato=2019,
        )
        apoio = self._criar_item(
            2,
            natureza=ItemImportacaoLote.Natureza.FRAGMENTO_NORMATIVO,
            numero_sugerido_texto="9321",
            ano_sugerido_texto=2019,
        )

        _vincular_documentos_apoio(self.lote)
        apoio.refresh_from_db()

        self.assertIsNone(apoio.documento_principal_sugerido)
        self.assertIsNone(apoio.documento_principal_candidato)

    def test_modelo_rejeita_vinculo_confirmado_entre_lotes(self):
        outro_lote = self._criar_lote("Outro lote")
        principal_externo = self._criar_item(
            1,
            lote=outro_lote,
            natureza=ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL,
            numero_candidato="9321",
            ano_candidato=2019,
        )
        apoio = self._criar_item(
            2,
            natureza=ItemImportacaoLote.Natureza.ANEXO_NORMATIVO,
        )
        apoio.documento_principal_candidato = principal_externo

        with self.assertRaises(ValidationError):
            apoio.full_clean()

    def test_api_expoe_sugestoes_divergencias_e_vinculos_distintos(self):
        principal = self._criar_item(
            1,
            natureza=ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL,
            numero_candidato="9321",
            ano_candidato=2019,
        )
        apoio = self._criar_item(
            2,
            natureza=ItemImportacaoLote.Natureza.ANEXO_NORMATIVO,
            numero_sugerido_texto="9321",
            ano_sugerido_texto=2019,
            fontes_sugestoes={"numero_sugerido_texto": "texto_primeiras_paginas"},
            divergencias_metadados=[{"campo": "ano_candidato"}],
            documento_principal_sugerido=principal,
        )

        dados = _item_json(apoio)

        self.assertEqual(dados["numero_sugerido_texto"], "9321")
        self.assertEqual(dados["ano_sugerido_texto"], 2019)
        self.assertEqual(dados["divergencias_metadados"], [{"campo": "ano_candidato"}])
        self.assertEqual(dados["documento_principal_sugerido"], principal.pk)
        self.assertIsNone(dados["documento_principal_candidato"])

    def test_arquivo_malformado_real_retorna_manual_sem_excecao(self):
        with NamedTemporaryFile(suffix=".pdf") as arquivo:
            arquivo.write(b"nao e um pdf")
            arquivo.flush()

            diagnostico = diagnosticar_pdf(arquivo.name)

        self.assertEqual(diagnostico.rota_sugerida, "manual")
