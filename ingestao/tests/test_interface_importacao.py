from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from ingestao.models import ImportacaoLote


def montar_zip() -> bytes:
    memoria = BytesIO()
    with ZipFile(memoria, "w", ZIP_DEFLATED) as arquivo:
        arquivo.writestr("Lote/Valinhos/lei_123_2024.pdf", b"%PDF-1.4\n%%EOF")
    return memoria.getvalue()


class TestesInterfaceImportacao(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="equipe",
            password="segredo-forte",
            is_staff=True,
        )
        self.client.force_login(self.usuario)

    def test_formulario_exige_usuario_autenticado(self):
        self.client.logout()
        resposta = self.client.get(reverse("nova_importacao"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/admin/login/", resposta.url)

    def test_formulario_bloqueia_usuario_sem_perfil_de_equipe(self):
        usuario_comum = get_user_model().objects.create_user(
            username="comum",
            password="segredo-forte",
            is_staff=False,
        )
        self.client.force_login(usuario_comum)
        resposta = self.client.get(reverse("nova_importacao"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/admin/login/", resposta.url)

    def test_recebe_zip_sem_inspecao_automatica(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            resposta = self.client.post(
                reverse("nova_importacao"),
                {
                    "titulo": "Corpus Valinhos",
                    "descricao": "Lote recebido pela interface.",
                    "origem_recebimento": "Prefeitura Municipal",
                    "uf_padrao": "SP",
                    "arquivo_zip": SimpleUploadedFile(
                        "valinhos.zip",
                        montar_zip(),
                        content_type="application/zip",
                    ),
                },
            )

            lote = ImportacaoLote.objects.get()
            self.assertRedirects(
                resposta,
                reverse("detalhe_importacao_web", kwargs={"lote_id": lote.pk}),
            )
            self.assertEqual(lote.nome_original, "valinhos.zip")
            self.assertEqual(lote.status, ImportacaoLote.Status.RECEBIDO)
            self.assertTrue(lote.sha256)
            self.assertTrue(lote.parametros["origem_interface"])

    def test_nome_original_remove_componentes_de_caminho(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            self.client.post(
                reverse("nova_importacao"),
                {
                    "titulo": "Corpus Valinhos",
                    "origem_recebimento": "Prefeitura Municipal",
                    "uf_padrao": "SP",
                    "arquivo_zip": SimpleUploadedFile(
                        "C:\\temporario\\valinhos.zip",
                        montar_zip(),
                        content_type="application/zip",
                    ),
                },
            )
        self.assertEqual(ImportacaoLote.objects.get().nome_original, "valinhos.zip")

    def test_rejeita_arquivo_sem_estrutura_zip(self):
        resposta = self.client.post(
            reverse("nova_importacao"),
            {
                "titulo": "Corpus inválido",
                "origem_recebimento": "Equipe municipal",
                "uf_padrao": "SP",
                "arquivo_zip": SimpleUploadedFile(
                    "invalido.zip",
                    b"PK-nao-e-zip",
                    content_type="application/zip",
                ),
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "estrutura ZIP válida")
        self.assertFalse(ImportacaoLote.objects.exists())

    def test_detalhe_exibe_lote(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            lote = ImportacaoLote.objects.create(
                titulo="Corpus de teste",
                origem_recebimento="Equipe",
                uf_padrao="SP",
                arquivo_zip=SimpleUploadedFile("teste.zip", montar_zip()),
            )
            resposta = self.client.get(
                reverse("detalhe_importacao_web", kwargs={"lote_id": lote.pk})
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Corpus de teste")
        self.assertContains(resposta, lote.sha256)
        self.assertContains(resposta, "Inspecionar ZIP")

    def test_inspeciona_lote_recebido_pela_interface(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            lote = ImportacaoLote.objects.create(
                titulo="Corpus de teste",
                origem_recebimento="Equipe",
                uf_padrao="SP",
                arquivo_zip=SimpleUploadedFile("teste.zip", montar_zip()),
            )
            resposta = self.client.post(
                reverse("inspecionar_importacao_web", kwargs={"lote_id": lote.pk})
            )
            lote.refresh_from_db()

        self.assertRedirects(
            resposta,
            reverse("detalhe_importacao_web", kwargs={"lote_id": lote.pk}),
        )
        self.assertEqual(lote.status, ImportacaoLote.Status.INSPECIONADO)
        self.assertEqual(lote.itens.count(), 1)

    def test_inspecao_web_aceita_apenas_post(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            lote = ImportacaoLote.objects.create(
                titulo="Corpus de teste",
                origem_recebimento="Equipe",
                uf_padrao="SP",
                arquivo_zip=SimpleUploadedFile("teste.zip", montar_zip()),
            )
            resposta = self.client.get(
                reverse("inspecionar_importacao_web", kwargs={"lote_id": lote.pk})
            )
        self.assertEqual(resposta.status_code, 405)
