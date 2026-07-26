from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from applications.models import (
    AplicacaoMunicipal,
    DocumentoNormativo,
    Municipio,
    TipoNormativo,
    VersaoDocumento,
)
from versionamento.models import ClassificacaoVersao, RelacaoVersoes


class BaseVersionamentoTeste(TestCase):
    def setUp(self):
        self.municipio = Municipio.objects.create(nome="Jundiaí", uf="SP")
        self.aplicacao = AplicacaoMunicipal.objects.create(
            municipio=self.municipio,
            titulo="Aplicação Jundiaí",
        )
        self.tipo = TipoNormativo.objects.get(codigo="lei_complementar")
        self.documento = DocumentoNormativo.objects.create(
            aplicacao=self.aplicacao,
            tipo=self.tipo,
            numero="606",
            ano=2021,
            titulo="Código de Obras e Edificações",
        )
        self.usuario = get_user_model().objects.create_user(username="revisor", password="teste")

    def criar_versao(self, numero: int, nome: str) -> VersaoDocumento:
        return VersaoDocumento.objects.create(
            documento=self.documento,
            versao=numero,
            arquivo=SimpleUploadedFile(nome, f"%PDF-1.4\n{numero}\n".encode(), "application/pdf"),
            mime_type="application/pdf",
        )


class TesteClassificacaoVersao(BaseVersionamentoTeste):
    def test_confirmacao_exige_responsavel_data_e_justificativa(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao = self.criar_versao(1, "consolidacao.pdf")
            classificacao = ClassificacaoVersao(
                versao_documento=versao,
                natureza=ClassificacaoVersao.Natureza.CONSOLIDACAO_OFICIAL,
                estado=ClassificacaoVersao.Estado.CONFIRMADA,
            )
            with self.assertRaises(ValidationError):
                classificacao.full_clean()

    def test_classificacao_confirmada_preserva_metadados_normativos(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            versao = self.criar_versao(1, "consolidacao.pdf")
            classificacao = ClassificacaoVersao(
                versao_documento=versao,
                natureza=ClassificacaoVersao.Natureza.CONSOLIDACAO_OFICIAL,
                data_referencia_normativa=date(2024, 10, 17),
                referencia_atualizacao="LC nº 633/2024",
                estado=ClassificacaoVersao.Estado.CONFIRMADA,
                justificativa="Cabeçalho da consolidação informa atualização expressa.",
                confirmado_por=self.usuario,
                confirmado_em=timezone.now(),
            )
            classificacao.full_clean()
            classificacao.save()
            self.assertEqual(versao.classificacao_normativa, classificacao)


class TesteRelacaoVersoes(BaseVersionamentoTeste):
    def test_sucessao_exige_destino_posterior_do_mesmo_documento(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            anterior = self.criar_versao(1, "2023.pdf")
            posterior = self.criar_versao(2, "2024.pdf")
            relacao = RelacaoVersoes(
                versao_origem=anterior,
                versao_destino=posterior,
                tipo=RelacaoVersoes.Tipo.SUCESSAO,
                justificativa="Consolidação atualizada.",
            )
            relacao.full_clean()
            relacao.save()
            self.assertEqual(RelacaoVersoes.objects.count(), 1)

            inversa = RelacaoVersoes(
                versao_origem=posterior,
                versao_destino=anterior,
                tipo=RelacaoVersoes.Tipo.SUCESSAO,
                justificativa="Ordem inválida.",
            )
            with self.assertRaises(ValidationError):
                inversa.full_clean()

    def test_comando_registra_classificacao_e_relacao_confirmadas(self):
        with TemporaryDirectory() as diretorio, self.settings(MEDIA_ROOT=Path(diretorio)):
            anterior = self.criar_versao(1, "2023.pdf")
            posterior = self.criar_versao(2, "2024.pdf")
            call_command(
                "classificar_relacao_versoes",
                destino=posterior.pk,
                origem=anterior.pk,
                natureza=ClassificacaoVersao.Natureza.CONSOLIDACAO_OFICIAL,
                tipo_relacao=RelacaoVersoes.Tipo.SUCESSAO,
                data_referencia=date(2024, 10, 17),
                referencia_atualizacao="LC nº 633/2024",
                justificativa="Atualização declarada na fonte.",
                fonte="cabeçalho do documento",
                usuario=self.usuario.username,
                confirmar=True,
            )
            classificacao = ClassificacaoVersao.objects.get(versao_documento=posterior)
            relacao = RelacaoVersoes.objects.get(
                versao_origem=anterior,
                versao_destino=posterior,
            )
            self.assertEqual(classificacao.estado, ClassificacaoVersao.Estado.CONFIRMADA)
            self.assertEqual(relacao.estado, RelacaoVersoes.Estado.CONFIRMADA)
