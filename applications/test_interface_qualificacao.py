import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

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


class TestesInterfaceQualificacao(TestCase):
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
            status=DocumentoNormativo.Status.VERIFICADO,
        )
        self._diretorio = TemporaryDirectory()
        self.addCleanup(self._diretorio.cleanup)
        self._settings = self.settings(MEDIA_ROOT=Path(self._diretorio.name))
        self._settings.enable()
        self.addCleanup(self._settings.disable)
        self.versao = VersaoDocumento.objects.create(
            documento=self.documento,
            arquivo=SimpleUploadedFile(
                "plano-diretor.pdf",
                b"%PDF-1.7\nconteudo",
                "application/pdf",
            ),
            mime_type="application/pdf",
        )
        self.processamento = ProcessamentoDocumento.objects.create(
            versao_documento=self.versao,
            etapa=ProcessamentoDocumento.Etapa.QUALIFICACAO,
            status=ProcessamentoDocumento.Status.CONCLUIDO,
            rota_documento=ProcessamentoDocumento.RotaDocumento.MISTO,
            ferramenta="conversor-his",
            versao_ferramenta="0.7.3",
            versao_codigo="abc123",
            parametros={"min_native_chars": 40},
            metricas={
                "paginas_total": 2,
                "rotas": {"native": 1, "ocr": 1},
            },
        )
        self.pagina_nativa = DiagnosticoPagina.objects.create(
            processamento=self.processamento,
            numero_pagina=1,
            rota="native",
            tipo_pagina="text",
            possui_texto_nativo=True,
            quantidade_caracteres=1200,
            dados_tecnicos={"layout_character_count": 1200},
        )
        self.pagina_ocr = DiagnosticoPagina.objects.create(
            processamento=self.processamento,
            numero_pagina=2,
            rota="ocr",
            tipo_pagina="unknown",
            quantidade_imagens=1,
            avisos=["camada textual insuficiente"],
        )
        conteudo = json.dumps(
            {"page_count": 2, "pages": [{"page_number": 1}, {"page_number": 2}]},
            ensure_ascii=False,
        ).encode("utf-8")
        self.artefato = ArtefatoProcessado(
            processamento=self.processamento,
            tipo=ArtefatoProcessado.Tipo.DIAGNOSTICO_JSON,
            sha256="a" * 64,
            tamanho_bytes=len(conteudo),
            mime_type="application/json",
        )
        self.artefato.arquivo.save("diagnostico.json", ContentFile(conteudo), save=False)
        self.artefato.save()

    def test_painel_exibe_indicadores_e_processamento(self):
        resposta = self.client.get(reverse("inicio"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Páginas diagnosticadas")
        self.assertContains(resposta, "Plano Diretor")

    def test_navegacao_aplicacao_documento_processamento(self):
        for nome, argumentos, texto in (
            ("lista_aplicacoes", [], "Aplicações municipais"),
            ("detalhe_aplicacao", [self.aplicacao.pk], "Corpus normativo"),
            ("detalhe_documento", [self.documento.pk], "Processamentos e artefatos"),
            ("detalhe_processamento", [self.processamento.pk], "Páginas diagnosticadas"),
            ("detalhe_pagina", [self.pagina_nativa.pk], "Dados técnicos estruturados"),
        ):
            resposta = self.client.get(reverse(nome, args=argumentos))
            self.assertEqual(resposta.status_code, 200)
            self.assertContains(resposta, texto)

    def test_filtro_de_rota_limita_paginas(self):
        resposta = self.client.get(
            reverse("detalhe_processamento", args=[self.processamento.pk]),
            {"rota": "ocr"},
        )

        self.assertContains(resposta, ">2</a>", html=False)
        self.assertNotContains(resposta, ">1</a>", html=False)

    def test_artefato_json_e_exibido_e_pode_ser_baixado(self):
        detalhe = self.client.get(reverse("detalhe_artefato", args=[self.artefato.pk]))
        download = self.client.get(reverse("baixar_artefato", args=[self.artefato.pk]))

        self.assertEqual(detalhe.status_code, 200)
        self.assertContains(detalhe, "&quot;page_count&quot;: 2", html=False)
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download.headers["Content-Disposition"])
        download.close()
