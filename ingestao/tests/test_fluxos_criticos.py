"""Testes de integração para os fluxos críticos de ingestão.

Cobre os cenários de maior risco:
- ZIP corrompido (BadZipFile): deve levar o lote a FALHOU com mensagem classificada.
- Transição de estado inválida: confirmar sem inspecionar deve ser recusado com 409.
- Reinspeção idempotente: inspecionar um lote FALHOU deve ser permitido e reprocessar itens.
- Duplicatas intralote: conteúdo idêntico dentro do mesmo ZIP é detectado corretamente.
- PDF sem assinatura válida: item vai para revisão e não pode ser marcado como pronto.
"""
from __future__ import annotations

from io import BytesIO
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ingestao.models import ImportacaoLote, ItemImportacaoLote

TOKEN = "segredo-fluxos-criticos"
CABECALHO = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


def _montar_zip(entradas: list[tuple[str, bytes]]) -> bytes:
    """Cria um ZIP em memória com as entradas especificadas como (caminho, conteúdo)."""
    memoria = BytesIO()
    with ZipFile(memoria, "w", ZIP_DEFLATED) as zf:
        for caminho, conteudo in entradas:
            zf.writestr(caminho, conteudo)
    return memoria.getvalue()


@override_settings(API_INGESTAO_TOKEN=TOKEN, INGESTAO_CONFIANCA_AUTOMATICA=0.8)
class TestesFluxosCriticos(TestCase):
    def setUp(self):
        self.diretorio = TemporaryDirectory()
        self.cfg = override_settings(
            MEDIA_ROOT=self.diretorio.name,
            PROTOCOL_DATA_ROOT=self.diretorio.name,
        )
        self.cfg.enable()

    def tearDown(self):
        self.cfg.disable()
        self.diretorio.cleanup()

    def _receber(self, conteudo: bytes, uf: str = "SP") -> ImportacaoLote:
        upload = SimpleUploadedFile("lote.zip", conteudo, "application/zip")
        resposta = self.client.post(
            reverse("api_criar_importacao"),
            {
                "arquivo_zip": upload,
                "titulo": "Lote de teste",
                "origem_recebimento": "testes automatizados",
                "uf_padrao": uf,
            },
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 201)
        return ImportacaoLote.objects.get(pk=resposta.json()["id"])

    def _inspecionar(self, lote: ImportacaoLote) -> int:
        resposta = self.client.post(
            reverse("api_inspecionar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        return resposta.status_code

    # ------------------------------------------------------------------
    # ZIP corrompido → lote marcado como FALHOU
    # ------------------------------------------------------------------

    def test_zip_corrompido_marca_lote_como_falhou(self):
        lote = self._receber(b"PK\x03\x04dados corrompidos que nao sao zip valido")
        status = self._inspecionar(lote)
        self.assertEqual(status, 422)
        lote.refresh_from_db()
        self.assertEqual(lote.status, ImportacaoLote.Status.FALHOU)
        self.assertTrue(lote.mensagem_erro)

    def test_zip_corrompido_registra_categoria_tecnica_na_resposta(self):
        lote = self._receber(b"PK\x03\x04dados corrompidos")
        resposta = self.client.post(
            reverse("api_inspecionar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 422)
        corpo = resposta.json()
        self.assertIn("erro", corpo)
        self.assertIn("lote", corpo)

    # ------------------------------------------------------------------
    # Transição de estado inválida
    # ------------------------------------------------------------------

    def test_confirmar_lote_nao_inspecionado_retorna_409(self):
        lote = self._receber(
            _montar_zip([("Jarinu/Lei-1-2024.pdf", b"%PDF-1.4\nconteudo\n%%EOF")])
        )
        # Lote está em RECEBIDO — confirmar sem inspecionar deve ser recusado.
        resposta = self.client.post(
            reverse("api_confirmar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 409)
        corpo = resposta.json()
        self.assertIn("erro", corpo)
        self.assertIn("governanca", corpo.get("categoria", ""))

    def test_inspecionar_lote_confirmado_retorna_409(self):
        zip_valido = _montar_zip([("Jarinu/Lei-1-2024.pdf", b"%PDF-1.4\nconteudo\n%%EOF")])
        lote = self._receber(zip_valido)
        # Definir status manualmente para CONFIRMADO para testar a transição proibida.
        ImportacaoLote.objects.filter(pk=lote.pk).update(status=ImportacaoLote.Status.CONFIRMADO)
        lote.refresh_from_db()

        resposta = self.client.post(
            reverse("api_inspecionar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        self.assertEqual(resposta.status_code, 409)
        corpo = resposta.json()
        self.assertIn("erro", corpo)
        self.assertIn("governanca", corpo.get("categoria", ""))

    # ------------------------------------------------------------------
    # Reinspeção idempotente: lote FALHOU pode ser reinspecionado
    # ------------------------------------------------------------------

    def test_reinspecionar_lote_falhou_e_permitido(self):
        lote = self._receber(b"PK\x03\x04dados corrompidos")
        # Primeira inspeção falha.
        self._inspecionar(lote)
        lote.refresh_from_db()
        self.assertEqual(lote.status, ImportacaoLote.Status.FALHOU)

        # Mudar para um ZIP válido não é possível (imutabilidade), mas podemos verificar
        # que a máquina de estados permite a transição FALHOU → INSPECIONANDO.
        # A reinspeção vai falhar novamente, mas a transição deve ser aceita.
        resposta = self.client.post(
            reverse("api_inspecionar_importacao", kwargs={"lote_id": lote.pk}),
            **CABECALHO,
        )
        # Aceita a transição (mesmo que o conteúdo ainda falhe), não retorna 409.
        self.assertNotEqual(resposta.status_code, 409)

    # ------------------------------------------------------------------
    # Duplicatas intralote
    # ------------------------------------------------------------------

    def test_duplicata_no_mesmo_zip_detectada_na_inspecao(self):
        pdf = b"%PDF-1.4\nconteudo duplicado\n%%EOF"
        zip_com_dups = _montar_zip([
            ("Jarinu/Lei-1-2024.pdf", pdf),
            ("Jarinu/copia-Lei-1-2024.pdf", pdf),
        ])
        lote = self._receber(zip_com_dups)
        status = self._inspecionar(lote)
        self.assertEqual(status, 200)
        lote.refresh_from_db()
        self.assertEqual(lote.status, ImportacaoLote.Status.INSPECIONADO)
        duplicados = lote.itens.filter(estado=ItemImportacaoLote.Estado.DUPLICADO)
        self.assertEqual(duplicados.count(), 1)

    def test_duplicatas_registram_referencia_ao_item_original(self):
        pdf = b"%PDF-1.4\nconteudo duplicado\n%%EOF"
        zip_com_dups = _montar_zip([
            ("Jarinu/Lei-1-2024.pdf", pdf),
            ("Jarinu/copia-Lei-1-2024.pdf", pdf),
        ])
        lote = self._receber(zip_com_dups)
        self._inspecionar(lote)
        duplicado = lote.itens.get(estado=ItemImportacaoLote.Estado.DUPLICADO)
        self.assertIsNotNone(duplicado.duplicado_de)
        self.assertNotEqual(duplicado.pk, duplicado.duplicado_de.pk)

    # ------------------------------------------------------------------
    # PDF com assinatura inválida → revisão, não pode ser marcado pronto
    # ------------------------------------------------------------------

    def test_pdf_sem_assinatura_valida_vai_para_revisao(self):
        zip_com_invalido = _montar_zip([
            ("Jarinu/Lei-1-2024.pdf", b"este nao e um pdf"),
        ])
        lote = self._receber(zip_com_invalido)
        self._inspecionar(lote)
        item = lote.itens.get()
        self.assertEqual(item.estado, ItemImportacaoLote.Estado.REVISAO)
        self.assertFalse(item.assinatura_pdf_valida)

    def test_pdf_com_assinatura_valida_pode_ser_classificado(self):
        zip_valido = _montar_zip([
            ("Jarinu/Lei-1-2024.pdf", b"%PDF-1.4\nconteudo\n%%EOF"),
        ])
        lote = self._receber(zip_valido)
        status = self._inspecionar(lote)
        self.assertEqual(status, 200)
        item = lote.itens.get()
        self.assertTrue(item.assinatura_pdf_valida)

    # ------------------------------------------------------------------
    # Reinspeção limpa itens antigos (idempotência da inspeção)
    # ------------------------------------------------------------------

    def test_reinspecionar_lote_inspecionado_limpa_itens_anteriores(self):
        zip_com_um = _montar_zip([
            ("Jarinu/Lei-1-2024.pdf", b"%PDF-1.4\nprimeiro\n%%EOF"),
        ])
        lote = self._receber(zip_com_um)
        self._inspecionar(lote)
        lote.refresh_from_db()
        self.assertEqual(lote.itens.count(), 1)

        # Segunda inspeção deve reprocessar os itens do mesmo ZIP.
        status = self._inspecionar(lote)
        self.assertEqual(status, 200)
        lote.refresh_from_db()
        self.assertEqual(lote.itens.count(), 1)
