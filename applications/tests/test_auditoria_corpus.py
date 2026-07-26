from hashlib import sha256

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction

from applications.models import (
    AdjudicacaoDocumental,
    AplicacaoMunicipal,
    ArtigoNormativo,
    AtoNormativo,
    DocumentoNormativo,
    Municipio,
    OcorrenciaDocumental,
    ReleaseCorpus,
    ReleaseCorpusDocumento,
    TipoNormativo,
    VersaoDocumento,
)


@pytest.fixture
def versao_documento(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    municipio = Municipio.objects.create(nome="Município Teste", uf="SP")
    aplicacao = AplicacaoMunicipal.objects.create(
        municipio=municipio,
        titulo="Aplicação de teste",
    )
    tipo = TipoNormativo.objects.create(
        codigo="lei_teste",
        nome="Lei de teste",
        sigla="LT",
        esfera=TipoNormativo.Esfera.MUNICIPAL,
        fonte_normativa="https://example.test/tipo",
        dispositivo_fonte="Configuração de teste",
    )
    documento = DocumentoNormativo.objects.create(
        aplicacao=aplicacao,
        tipo=tipo,
        numero="1",
        ano=2026,
        titulo="Lei de teste",
    )
    return VersaoDocumento.objects.create(
        documento=documento,
        versao=1,
        arquivo=SimpleUploadedFile("lei.pdf", b"conteudo normativo", content_type="application/pdf"),
    )


@pytest.fixture
def ato(versao_documento):
    return AtoNormativo.objects.create(
        versao_documento=versao_documento,
        identificador="sp_municipio_teste_lei_1_2026",
        especie="Lei",
        numero="1",
        ano=2026,
        pagina_inicial=1,
        pagina_final=4,
    )


@pytest.mark.django_db
def test_artigo_calcula_hash_do_texto(ato):
    texto = "Art. 1º Esta lei estabelece regras de teste."
    artigo = ArtigoNormativo.objects.create(
        ato=ato,
        identificador="sp_municipio_teste_lei_1_2026_art_001",
        rotulo="Art. 1º",
        numero_textual="1",
        numero_normalizado=1,
        pagina_inicial=1,
        pagina_final=1,
        fonte_pos_bloco=True,
        texto=texto,
    )

    assert artigo.sha256_texto == sha256(texto.encode("utf-8")).hexdigest()


@pytest.mark.django_db
def test_intervalo_invalido_de_paginas_do_ato_e_rejeitado(versao_documento):
    with pytest.raises(IntegrityError), transaction.atomic():
        AtoNormativo.objects.create(
            versao_documento=versao_documento,
            identificador="ato_intervalo_invalido",
            pagina_inicial=5,
            pagina_final=4,
        )


@pytest.mark.django_db
def test_numero_de_artigo_nao_pode_repetir_no_mesmo_ato(ato):
    dados = {
        "ato": ato,
        "rotulo": "Art. 1º",
        "numero_textual": "1",
        "numero_normalizado": 1,
        "pagina_inicial": 1,
        "pagina_final": 1,
        "texto": "Texto do artigo.",
    }
    ArtigoNormativo.objects.create(
        identificador="artigo_unico_1",
        **dados,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ArtigoNormativo.objects.create(
            identificador="artigo_unico_2",
            **dados,
        )


@pytest.mark.django_db
def test_ocorrencia_critica_aberta_bloqueia_release(versao_documento):
    ocorrencia = OcorrenciaDocumental.objects.create(
        versao_documento=versao_documento,
        categoria="pagina_ausente",
        severidade=OcorrenciaDocumental.Severidade.CRITICA,
        descricao="Uma página do corpo normativo não foi localizada.",
    )

    assert ocorrencia.bloqueia_release is True

    ocorrencia.estado = OcorrenciaDocumental.Estado.RESOLVIDA
    ocorrencia.save(update_fields=["estado", "atualizado_em"])

    assert ocorrencia.bloqueia_release is False


@pytest.mark.django_db
def test_adjudicacao_e_unica_por_ocorrencia(versao_documento):
    usuario = get_user_model().objects.create_user(username="revisor", password="teste-seguro")
    ocorrencia = OcorrenciaDocumental.objects.create(
        versao_documento=versao_documento,
        categoria="sequencia_irregular",
        severidade=OcorrenciaDocumental.Severidade.ALTA,
        descricao="A sequência dos artigos precisa de adjudicação.",
    )
    AdjudicacaoDocumental.objects.create(
        ocorrencia=ocorrencia,
        decisao="Preservar a irregularidade original.",
        fundamento="A numeração foi confirmada visualmente na fonte.",
        estado_resultante=OcorrenciaDocumental.Estado.ACEITA,
        responsavel=usuario,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        AdjudicacaoDocumental.objects.create(
            ocorrencia=ocorrencia,
            decisao="Decisão duplicada.",
            fundamento="Não aplicável.",
            estado_resultante=OcorrenciaDocumental.Estado.RESOLVIDA,
            responsavel=usuario,
        )


@pytest.mark.django_db
def test_release_nao_repete_versao_documental(versao_documento):
    release = ReleaseCorpus.objects.create(
        aplicacao=versao_documento.documento.aplicacao,
        versao="0.1.0",
    )
    ReleaseCorpusDocumento.objects.create(
        release=release,
        versao_documento=versao_documento,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ReleaseCorpusDocumento.objects.create(
            release=release,
            versao_documento=versao_documento,
        )


# ------------------------------------------------------------------
# Testes de motivos_bloqueio e pode_ser_liberado
# ------------------------------------------------------------------


@pytest.mark.django_db
def test_release_sem_ocorrencias_e_sem_atos_esta_bloqueado(versao_documento):
    """Release com versão documental sem atos normativos deve ser bloqueado por traceabilidade."""
    release = ReleaseCorpus.objects.create(
        aplicacao=versao_documento.documento.aplicacao,
        versao="0.2.0",
    )
    ReleaseCorpusDocumento.objects.create(release=release, versao_documento=versao_documento)

    motivos = release.motivos_bloqueio()

    assert not release.pode_ser_liberado
    assert any("ato normativo" in motivo.lower() for motivo in motivos)


@pytest.mark.django_db
def test_release_com_atos_e_sem_ocorrencias_criticas_pode_ser_liberado(versao_documento, ato):
    """Release com atos registrados e sem ocorrências críticas abertas deve ser liberado."""
    release = ReleaseCorpus.objects.create(
        aplicacao=versao_documento.documento.aplicacao,
        versao="0.3.0",
    )
    ReleaseCorpusDocumento.objects.create(release=release, versao_documento=versao_documento)

    motivos = release.motivos_bloqueio()

    assert motivos == []
    assert release.pode_ser_liberado


@pytest.mark.django_db
def test_release_com_ocorrencia_critica_aberta_e_com_atos_esta_bloqueado(versao_documento, ato):
    """Release com ocorrência crítica aberta deve ser bloqueado mesmo que haja atos."""
    release = ReleaseCorpus.objects.create(
        aplicacao=versao_documento.documento.aplicacao,
        versao="0.4.0",
    )
    ReleaseCorpusDocumento.objects.create(release=release, versao_documento=versao_documento)
    OcorrenciaDocumental.objects.create(
        versao_documento=versao_documento,
        categoria="pagina_ausente",
        severidade=OcorrenciaDocumental.Severidade.CRITICA,
        descricao="Teste.",
    )

    motivos = release.motivos_bloqueio()

    assert not release.pode_ser_liberado
    assert any("crítica" in motivo.lower() for motivo in motivos)


@pytest.mark.django_db
def test_motivos_bloqueio_lista_ocorrencias_e_traceabilidade_em_conjunto(
    versao_documento,
):
    """motivos_bloqueio() deve listar todos os problemas simultaneamente."""
    release = ReleaseCorpus.objects.create(
        aplicacao=versao_documento.documento.aplicacao,
        versao="0.5.0",
    )
    ReleaseCorpusDocumento.objects.create(release=release, versao_documento=versao_documento)
    # Sem atos e com ocorrência crítica aberta: dois motivos de bloqueio.
    OcorrenciaDocumental.objects.create(
        versao_documento=versao_documento,
        categoria="pagina_ausente",
        severidade=OcorrenciaDocumental.Severidade.CRITICA,
        descricao="Teste.",
    )

    motivos = release.motivos_bloqueio()

    assert len(motivos) == 2
    assert not release.pode_ser_liberado


@pytest.mark.django_db
def test_ocorrencia_critica_resolvida_nao_bloqueia_release_com_atos(versao_documento, ato):
    """Ocorrência crítica resolvida não deve bloquear o release."""
    release = ReleaseCorpus.objects.create(
        aplicacao=versao_documento.documento.aplicacao,
        versao="0.6.0",
    )
    ReleaseCorpusDocumento.objects.create(release=release, versao_documento=versao_documento)
    ocorrencia = OcorrenciaDocumental.objects.create(
        versao_documento=versao_documento,
        categoria="pagina_ausente",
        severidade=OcorrenciaDocumental.Severidade.CRITICA,
        descricao="Teste.",
        estado=OcorrenciaDocumental.Estado.RESOLVIDA,
    )

    assert ocorrencia.estado == OcorrenciaDocumental.Estado.RESOLVIDA
    assert release.motivos_bloqueio() == []
    assert release.pode_ser_liberado
