from __future__ import annotations

from hashlib import sha256
from io import StringIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError

from applications.models import (
    AnexoNormativo,
    AplicacaoMunicipal,
    ArtefatoProcessado,
    ArtigoNormativo,
    AtoNormativo,
    DocumentoNormativo,
    Municipio,
    OcorrenciaDocumental,
    ProcessamentoDocumento,
    ReleaseCorpus,
    ReleaseCorpusDocumento,
    TipoNormativo,
    VersaoDocumento,
)


@pytest.fixture
def versao_convertida(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    municipio = Municipio.objects.create(nome="Recife", uf="PE")
    aplicacao = AplicacaoMunicipal.objects.create(
        municipio=municipio,
        titulo="Aplicação Recife",
    )
    tipo = TipoNormativo.objects.create(
        codigo="lei_teste_cmd",
        nome="Lei",
        sigla="LEI",
        esfera=TipoNormativo.Esfera.MUNICIPAL,
        fonte_normativa="https://example.test/tipo",
        dispositivo_fonte="Configuração de teste",
    )
    documento = DocumentoNormativo.objects.create(
        aplicacao=aplicacao,
        tipo=tipo,
        numero="42",
        ano=2026,
        titulo="Lei nº 42/2026",
        status=DocumentoNormativo.Status.LIBERADO,
    )
    versao = VersaoDocumento.objects.create(
        documento=documento,
        versao=1,
        arquivo=SimpleUploadedFile("lei.pdf", b"%PDF-1.7 teste", content_type="application/pdf"),
    )
    processamento = ProcessamentoDocumento.objects.create(
        versao_documento=versao,
        etapa=ProcessamentoDocumento.Etapa.CONVERSAO,
        status=ProcessamentoDocumento.Status.CONCLUIDO,
        rota_documento=ProcessamentoDocumento.RotaDocumento.TEXTO_NATIVO,
        ferramenta="conversor-his",
        versao_ferramenta="1.0",
        versao_codigo="abc123",
    )
    markdown = (
        "# Lei nº 42/2026\n\n"
        "## Página 1\n\n"
        "Art. 1º Dispõe sobre a política habitacional.\n\n"
        "Artigo 2 Os programas serão regulamentados pelo Executivo.\n\n"
        "## Anexo I - Quadro de parâmetros\n\n"
        "Conteúdo do anexo.\n\n"
        "# Decreto nº 7/2025\n\n"
        "## Página 2\n\n"
        "Art. 1º Regulamenta procedimentos complementares.\n"
    )
    ArtefatoProcessado.objects.create(
        processamento=processamento,
        tipo=ArtefatoProcessado.Tipo.MARKDOWN,
        arquivo=SimpleUploadedFile("lei.md", markdown.encode("utf-8"), content_type="text/markdown"),
        sha256=sha256(markdown.encode("utf-8")).hexdigest(),
        tamanho_bytes=len(markdown.encode("utf-8")),
        mime_type="text/markdown",
    )
    return versao


@pytest.mark.django_db
def test_importar_atos_markdown_cria_registros_e_e_idempotente(versao_convertida):
    saida = StringIO()

    call_command("importar_atos_markdown", versao_convertida.pk, stdout=saida)

    assert AtoNormativo.objects.filter(versao_documento=versao_convertida).count() == 2
    assert ArtigoNormativo.objects.count() == 3
    assert AnexoNormativo.objects.count() == 1

    primeiro_ato = AtoNormativo.objects.filter(versao_documento=versao_convertida).order_by("pk").first()
    assert primeiro_ato is not None
    assert primeiro_ato.primeiro_artigo == "Art. 1º"
    assert primeiro_ato.ultimo_artigo == "Artigo 2"
    assert "2 ato(s) criado(s)" in saida.getvalue()

    saida = StringIO()
    call_command("importar_atos_markdown", versao_convertida.pk, stdout=saida)

    assert AtoNormativo.objects.filter(versao_documento=versao_convertida).count() == 2
    assert ArtigoNormativo.objects.count() == 3
    assert AnexoNormativo.objects.count() == 1
    assert "0 ato(s) criado(s), 2 ignorado(s)" in saida.getvalue()


@pytest.mark.django_db
def test_importar_atos_markdown_dry_run_nao_persiste(versao_convertida):
    saida = StringIO()

    call_command("importar_atos_markdown", versao_convertida.pk, dry_run=True, stdout=saida)

    assert AtoNormativo.objects.count() == 0
    assert ArtigoNormativo.objects.count() == 0
    assert AnexoNormativo.objects.count() == 0
    assert "dry-run" in saida.getvalue()


@pytest.mark.django_db
def test_criar_release_corpus_liga_versoes_liberadas(versao_convertida):
    saida = StringIO()

    call_command(
        "criar_release_corpus",
        versao_convertida.documento.aplicacao.pk,
        versao="2026.07",
        liberado=True,
        stdout=saida,
    )

    release = ReleaseCorpus.objects.get(aplicacao=versao_convertida.documento.aplicacao, versao="2026.07")
    assert release.estado == ReleaseCorpus.Estado.LIBERADO
    assert release.liberado_em is not None
    assert ReleaseCorpusDocumento.objects.filter(release=release, versao_documento=versao_convertida).exists()
    assert "Release criada com sucesso" in saida.getvalue()


@pytest.mark.django_db
def test_criar_release_corpus_aborta_com_ocorrencia_critica(versao_convertida):
    OcorrenciaDocumental.objects.create(
        versao_documento=versao_convertida,
        categoria="lacuna_documental",
        severidade=OcorrenciaDocumental.Severidade.CRITICA,
        estado=OcorrenciaDocumental.Estado.ABERTA,
        descricao="Há uma lacuna crítica pendente.",
        pagina=2,
    )

    with pytest.raises(CommandError, match="ocorrências críticas abertas"):
        call_command(
            "criar_release_corpus",
            versao_convertida.documento.aplicacao.pk,
            versao="2026.08",
        )

    assert not ReleaseCorpus.objects.filter(
        aplicacao=versao_convertida.documento.aplicacao,
        versao="2026.08",
    ).exists()
