import csv
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .manifesto import gerar_manifesto_csv, gerar_manifesto_json
from .models import (
    AplicacaoMunicipal,
    DocumentoNormativo,
    Municipio,
    TipoNormativo,
    VersaoDocumento,
)


class TestesPaginaInicial(TestCase):
    def test_pagina_inicial_responde_e_exibe_titulo(self):
        resposta = self.client.get(reverse("inicio"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Plataforma Protocolo HIS")


class BaseTesteCorpus(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Valinhos", uf="sp")
        self.aplicacao = AplicacaoMunicipal.objects.create(
            municipio=self.municipio,
            titulo="Aplicação piloto",
        )
        self.tipo_lei = TipoNormativo.objects.get(codigo="lei_ordinaria")
        self.tipo_decreto = TipoNormativo.objects.get(codigo="decreto_regulamentar")
        self.documento = DocumentoNormativo.objects.create(
            aplicacao=self.aplicacao,
            tipo=self.tipo_lei,
            numero="7.730",
            ano=2019,
            titulo="Plano Diretor",
        )


class TestesVersaoDocumento(BaseTesteCorpus):
    def test_upload_calcula_sha256_e_preserva_nome_original(self):
        conteudo = b"conteudo normativo de teste"

        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao = VersaoDocumento.objects.create(
                documento=self.documento,
                arquivo=SimpleUploadedFile("plano-diretor.pdf", conteudo, "application/pdf"),
                mime_type="application/pdf",
                origem_recebimento="Prefeitura Municipal",
            )

            self.assertEqual(versao.sha256, sha256(conteudo).hexdigest())
            self.assertEqual(versao.nome_original, "plano-diretor.pdf")
            self.assertEqual(versao.tamanho_bytes, len(conteudo))
            self.assertEqual(versao.situacao_ingestao, VersaoDocumento.SituacaoIngestao.ORIGINAL)
            self.assertIn(versao.sha256, versao.arquivo.name)

    def test_arquivo_vazio_e_rejeitado(self):
        with (
            TemporaryDirectory() as diretorio,
            self.settings(MEDIA_ROOT=Path(diretorio)),
            self.assertRaises(ValidationError),
        ):
            VersaoDocumento.objects.create(
                documento=self.documento,
                arquivo=SimpleUploadedFile("vazio.pdf", b"", "application/pdf"),
                mime_type="application/pdf",
            )

    def test_conteudo_repetido_e_marcado_como_duplicado(self):
        outro_documento = DocumentoNormativo.objects.create(
            aplicacao=self.aplicacao,
            tipo=self.tipo_decreto,
            numero="1",
            ano=2020,
            titulo="Documento repetido",
        )
        conteudo = b"mesmo conteudo"

        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            original = VersaoDocumento.objects.create(
                documento=self.documento,
                arquivo=SimpleUploadedFile("original.pdf", conteudo, "application/pdf"),
            )
            duplicado = VersaoDocumento.objects.create(
                documento=outro_documento,
                arquivo=SimpleUploadedFile("copia.pdf", conteudo, "application/pdf"),
            )

            self.assertEqual(duplicado.situacao_ingestao, VersaoDocumento.SituacaoIngestao.DUPLICADO)
            self.assertEqual(duplicado.duplicado_de, original)


class TestesCatalogoNormativo(TestCase):
    def test_catalogo_inicial_registra_fonte_e_dispositivo(self):
        tipo = TipoNormativo.objects.get(codigo="lei_complementar")

        self.assertEqual(tipo.nome, "Lei complementar")
        self.assertIn("lcp95", tipo.fonte_normativa.lower())
        self.assertIn("art", tipo.dispositivo_fonte.lower())


class TestesManifestoCorpus(BaseTesteCorpus):
    def test_manifestos_json_e_csv_reproduzem_metadados(self):
        conteudo = b"conteudo para manifesto"

        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            VersaoDocumento.objects.create(
                documento=self.documento,
                arquivo=SimpleUploadedFile("plano.pdf", conteudo, "application/pdf"),
                mime_type="application/pdf",
                origem_recebimento="Equipe municipal",
            )
            raiz = Path(diretorio)
            caminho_json = gerar_manifesto_json(self.aplicacao, raiz / "manifesto.json")
            caminho_csv = gerar_manifesto_csv(self.aplicacao, raiz / "manifesto.csv")

            dados_json = json.loads(caminho_json.read_text(encoding="utf-8"))
            with caminho_csv.open(encoding="utf-8-sig", newline="") as arquivo_csv:
                dados_csv = list(csv.DictReader(arquivo_csv))

            self.assertEqual(dados_json["aplicacao"]["municipio"], "Valinhos/SP")
            self.assertEqual(dados_json["arquivos"][0]["nome_original"], "plano.pdf")
            self.assertEqual(dados_csv[0]["sha256"], sha256(conteudo).hexdigest())
