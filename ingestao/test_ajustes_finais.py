from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from .admin import AdministracaoItemImportacaoLote
from .enriquecimento import _metadados_do_texto, diagnosticar_pdf
from .models import ImportacaoLote, ItemImportacaoLote


class PaginaSimulada:
    def __init__(self, texto: str):
        self.texto = texto

    def extract_text(self) -> str:
        return self.texto


class LeitorSimulado:
    def __init__(self, *textos: str):
        self.pages = [PaginaSimulada(texto) for texto in textos]


class TestesIdentidadeErota(SimpleTestCase):
    def test_compilacao_ignora_lei_atualizadora_e_recupera_identidade_do_ato(self):
        texto = (
            "[Texto compilado – atualizado até a Lei nº 10.177, de 13 de junho de 2024] "
            "LEI N.º 9.321, DE 11 DE NOVEMBRO DE 2019 Revisa o Plano Diretor."
        )

        numero, ano = _metadados_do_texto(texto)

        self.assertEqual(numero, "9.321")
        self.assertEqual(ano, 2019)

    @patch("ingestao.enriquecimento.PdfReader")
    def test_amostra_com_pagina_textual_e_pagina_vazia_recebe_rota_mista(self, pdf_reader):
        pdf_reader.return_value = LeitorSimulado("texto normativo " * 20, "")

        diagnostico = diagnosticar_pdf("documento-misto.pdf")

        self.assertEqual(diagnostico.rota_sugerida, "misto")
        self.assertEqual(diagnostico.caracteres_por_pagina[1], 0)
        self.assertTrue(any("combina páginas" in aviso for aviso in diagnostico.avisos))

    @patch("ingestao.enriquecimento.PdfReader")
    def test_amostra_com_todas_paginas_textuais_permanece_texto_nativo(self, pdf_reader):
        pdf_reader.return_value = LeitorSimulado("texto normativo " * 20, "outro texto " * 20)

        diagnostico = diagnosticar_pdf("documento-nativo.pdf")

        self.assertEqual(diagnostico.rota_sugerida, "texto_nativo")


class TestesVinculoSemantico(TestCase):
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

    def _principal_valido(self, indice: int = 1) -> ItemImportacaoLote:
        return self._criar_item(
            indice,
            natureza=ItemImportacaoLote.Natureza.NORMATIVO_MUNICIPAL,
            tipo_normativo_codigo="lei_ordinaria",
            numero_candidato="9321",
            ano_candidato=2019,
            titulo_candidato="Plano Diretor",
            estado=ItemImportacaoLote.Estado.PRONTO,
        )

    def test_vinculo_confirmado_rejeita_documento_de_apoio_como_principal(self):
        apoio_invalido = self._criar_item(
            1,
            natureza=ItemImportacaoLote.Natureza.ANEXO_NORMATIVO,
            numero_candidato="9321",
            ano_candidato=2019,
        )
        apoio = self._criar_item(2, natureza=ItemImportacaoLote.Natureza.ANEXO_NORMATIVO)
        apoio.documento_principal_candidato = apoio_invalido

        with self.assertRaises(ValidationError):
            apoio.full_clean()

    def test_vinculo_confirmado_rejeita_principal_duplicado(self):
        principal = self._principal_valido()
        principal.estado = ItemImportacaoLote.Estado.DUPLICADO
        principal.save(update_fields=["estado", "atualizado_em"])
        apoio = self._criar_item(2, natureza=ItemImportacaoLote.Natureza.ANEXO_NORMATIVO)
        apoio.documento_principal_candidato = principal

        with self.assertRaises(ValidationError):
            apoio.full_clean()

    def test_vinculo_sugerido_invalido_e_descartado_no_save(self):
        principal_invalido = self._criar_item(
            1,
            natureza=ItemImportacaoLote.Natureza.FRAGMENTO_NORMATIVO,
        )
        apoio = self._criar_item(2, natureza=ItemImportacaoLote.Natureza.ANEXO_NORMATIVO)
        apoio.documento_principal_sugerido = principal_invalido
        apoio.save()
        apoio.refresh_from_db()

        self.assertIsNone(apoio.documento_principal_sugerido)

    def test_vinculo_confirmado_aceita_principal_normativo_valido(self):
        principal = self._principal_valido()
        apoio = self._criar_item(2, natureza=ItemImportacaoLote.Natureza.ANEXO_NORMATIVO)
        apoio.documento_principal_candidato = principal

        apoio.full_clean()
        apoio.save()

        self.assertEqual(apoio.documento_principal_candidato, principal)

    def test_campos_automaticos_sao_somente_leitura_no_admin(self):
        somente_leitura = set(AdministracaoItemImportacaoLote.readonly_fields)

        self.assertTrue(
            {
                "numero_sugerido_texto",
                "ano_sugerido_texto",
                "fontes_sugestoes",
                "fontes_metadados",
                "divergencias_metadados",
                "documento_principal_sugerido",
            }.issubset(somente_leitura)
        )
