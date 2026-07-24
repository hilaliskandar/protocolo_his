from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import AplicacaoMunicipal, DocumentoNormativo, Municipio, VersaoDocumento


class PaginaInicialTests(TestCase):
    def test_pagina_inicial_responde_e_exibe_titulo(self):
        resposta = self.client.get(reverse("inicio"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Plataforma Protocolo HIS")


class VersaoDocumentoTests(TestCase):
    def test_upload_calcula_sha256_e_preserva_nome_original(self):
        municipio = Municipio.objects.create(nome="Valinhos", uf="sp")
        aplicacao = AplicacaoMunicipal.objects.create(
            municipio=municipio,
            titulo="Aplicação piloto",
        )
        documento = DocumentoNormativo.objects.create(
            aplicacao=aplicacao,
            tipo=DocumentoNormativo.Tipo.LEI,
            numero="7.730",
            ano=2019,
            titulo="Plano Diretor",
        )
        conteudo = b"conteudo normativo de teste"

        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao = VersaoDocumento.objects.create(
                documento=documento,
                arquivo=SimpleUploadedFile("plano-diretor.pdf", conteudo, "application/pdf"),
                mime_type="application/pdf",
            )

            self.assertEqual(versao.sha256, sha256(conteudo).hexdigest())
            self.assertEqual(versao.nome_original, "plano-diretor.pdf")
            self.assertEqual(versao.tamanho_bytes, len(conteudo))
            self.assertIn(versao.sha256, versao.arquivo.name)
