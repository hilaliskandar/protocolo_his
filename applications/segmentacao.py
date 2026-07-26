from __future__ import annotations

import json
import re
from bisect import bisect_right
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from time import monotonic
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import (
    AnexoNormativo,
    ArtefatoProcessado,
    ArtigoNormativo,
    AtoNormativo,
    OcorrenciaDocumental,
    ProcessamentoDocumento,
    VersaoDocumento,
)

VERSAO_SEGMENTADOR = "0.4.1"
FERRAMENTA_SEGMENTADOR = "segmentador-normativo"
CATEGORIA_PREFIXO = "segmentacao_"

PADRAO_ARTIGO = re.compile(
    r"(?im)^(?P<prefixo>\s{0,3}(?:#{1,6}\s*)?(?:\*\*|__)?\s*)"
    r"(?P<rotulo>Art(?:igo)?\.?\s*(?P<numero>\d+)(?:[º°o])?"
    r"(?:\s*[-–—]\s*(?P<sufixo>[A-Za-z]))?)"
    r"(?P<resto>[^\n]*?)(?:\*\*|__)?\s*$"
)
PADRAO_ANEXO = re.compile(
    r"(?im)^(?P<prefixo>\s{0,3}(?:#{1,6}\s*)?(?:\*\*|__)?\s*)"
    r"(?P<titulo>(?:ANEXO(?:\s+(?:ÚNICO|UNICO|[IVXLCDM]+|\d+))?"
    r"|QUADRO(?:\s+[IVXLCDM\d]+)?|TABELA(?:\s+[IVXLCDM\d]+)?"
    r"|MAPA(?:\s+[IVXLCDM\d]+)?|MEMORIAL\s+DESCRITIVO)[^\n]*?)"
    r"(?:\*\*|__)?\s*$"
)
PADRAO_PAGINA = re.compile(
    r"(?im)<!--\s*(?:page|p[áa]gina)\s*[:#]?\s*(\d+)\s*-->"
    r"|\[\[(?:PAGE|P[ÁA]GINA)\s+(\d+)\]\]"
    r"|^\s*---\s*(?:page|p[áa]gina)\s+(\d+)\s*---\s*$"
)


class ErroSegmentacao(RuntimeError):
    """Erro controlado durante a segmentação de unidades normativas."""


@dataclass(slots=True)
class ArtigoExtraido:
    rotulo: str
    numero_textual: str
    numero_normalizado: int
    sufixo: str
    texto: str
    inicio: int
    fim: int
    linha_inicial: int
    linha_final: int
    pagina_inicial: int
    pagina_final: int
    status_sequencia: str = ArtigoNormativo.StatusSequencia.REGULAR


@dataclass(slots=True)
class AnexoExtraido:
    titulo: str
    tipo: str
    texto: str
    inicio: int
    fim: int
    linha_inicial: int
    linha_final: int
    pagina_inicial: int
    pagina_final: int


@dataclass(slots=True)
class OcorrenciaExtraida:
    categoria: str
    severidade: str
    descricao: str
    pagina: int | None = None
    evidencias: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ResultadoSegmentacao:
    artigos: list[ArtigoExtraido]
    anexos: list[AnexoExtraido]
    ocorrencias: list[OcorrenciaExtraida]
    metricas: dict[str, Any]
    sha256_markdown: str

    def como_dict(self) -> dict[str, Any]:
        return {
            "versao_segmentador": VERSAO_SEGMENTADOR,
            "sha256_markdown": self.sha256_markdown,
            "metricas": self.metricas,
            "artigos": [asdict(item) for item in self.artigos],
            "anexos": [asdict(item) for item in self.anexos],
            "ocorrencias": [asdict(item) for item in self.ocorrencias],
        }


def _linha_em(texto: str, posicao: int) -> int:
    return texto.count("\n", 0, posicao) + 1


def _marcadores_pagina(texto: str) -> tuple[list[int], list[int]]:
    posicoes = [0]
    paginas = [1]
    for correspondencia in PADRAO_PAGINA.finditer(texto):
        numero = next(
            int(grupo) for grupo in correspondencia.groups() if grupo is not None
        )
        posicoes.append(correspondencia.start())
        paginas.append(numero)
    return posicoes, paginas


def _pagina_em(posicao: int, posicoes: list[int], paginas: list[int]) -> int:
    indice = bisect_right(posicoes, posicao) - 1
    return paginas[max(indice, 0)]


def _tipo_anexo(titulo: str) -> str:
    titulo_normalizado = titulo.upper()
    if titulo_normalizado.startswith("TABELA") or titulo_normalizado.startswith("QUADRO"):
        return AnexoNormativo.Tipo.TABELA
    if titulo_normalizado.startswith("MAPA"):
        return AnexoNormativo.Tipo.MAPA
    if titulo_normalizado.startswith("MEMORIAL DESCRITIVO"):
        return AnexoNormativo.Tipo.COORDENADAS
    return AnexoNormativo.Tipo.TEXTO


def _uniao_intervalos(intervalos: list[tuple[int, int]]) -> int:
    if not intervalos:
        return 0
    total = 0
    inicio_atual, fim_atual = sorted(intervalos)[0]
    for inicio, fim in sorted(intervalos)[1:]:
        if inicio <= fim_atual:
            fim_atual = max(fim_atual, fim)
        else:
            total += fim_atual - inicio_atual
            inicio_atual, fim_atual = inicio, fim
    return total + fim_atual - inicio_atual


def segmentar_markdown(markdown: str) -> ResultadoSegmentacao:
    """Segmenta artigos e anexos sem corrigir silenciosamente a fonte."""
    sha_markdown = sha256(markdown.encode("utf-8")).hexdigest()
    posicoes_pagina, paginas = _marcadores_pagina(markdown)
    marcadores: list[tuple[int, str, re.Match[str]]] = []
    marcadores.extend((item.start(), "artigo", item) for item in PADRAO_ARTIGO.finditer(markdown))
    marcadores.extend((item.start(), "anexo", item) for item in PADRAO_ANEXO.finditer(markdown))
    marcadores.sort(key=lambda item: item[0])

    artigos: list[ArtigoExtraido] = []
    anexos: list[AnexoExtraido] = []
    ocorrencias: list[OcorrenciaExtraida] = []
    intervalos: list[tuple[int, int]] = []

    for indice, (inicio, tipo, correspondencia) in enumerate(marcadores):
        fim = marcadores[indice + 1][0] if indice + 1 < len(marcadores) else len(markdown)
        bloco = markdown[inicio:fim].strip()
        if not bloco:
            continue
        linha_inicial = _linha_em(markdown, inicio)
        linha_final = _linha_em(markdown, max(fim - 1, inicio))
        pagina_inicial = _pagina_em(inicio, posicoes_pagina, paginas)
        pagina_final = _pagina_em(max(fim - 1, inicio), posicoes_pagina, paginas)
        intervalos.append((inicio, fim))

        if tipo == "artigo":
            numero = correspondencia.group("numero")
            sufixo = (correspondencia.group("sufixo") or "").upper()
            artigos.append(
                ArtigoExtraido(
                    rotulo=correspondencia.group("rotulo").strip(),
                    numero_textual=numero,
                    numero_normalizado=int(numero),
                    sufixo=sufixo,
                    texto=bloco,
                    inicio=inicio,
                    fim=fim,
                    linha_inicial=linha_inicial,
                    linha_final=linha_final,
                    pagina_inicial=pagina_inicial,
                    pagina_final=pagina_final,
                )
            )
        else:
            titulo = correspondencia.group("titulo").strip()
            anexos.append(
                AnexoExtraido(
                    titulo=titulo,
                    tipo=_tipo_anexo(titulo),
                    texto=bloco,
                    inicio=inicio,
                    fim=fim,
                    linha_inicial=linha_inicial,
                    linha_final=linha_final,
                    pagina_inicial=pagina_inicial,
                    pagina_final=pagina_final,
                )
            )

    if not artigos:
        ocorrencias.append(
            OcorrenciaExtraida(
                categoria="segmentacao_sem_artigos",
                severidade=OcorrenciaDocumental.Severidade.CRITICA,
                descricao="Nenhum cabeçalho de artigo foi reconhecido no Markdown.",
            )
        )

    vistos: dict[tuple[int, str], ArtigoExtraido] = {}
    duplicados: dict[tuple[int, str], list[ArtigoExtraido]] = {}
    for artigo in artigos:
        chave = (artigo.numero_normalizado, artigo.sufixo)
        if chave in vistos:
            vistos[chave].status_sequencia = ArtigoNormativo.StatusSequencia.DUPLICADO
            artigo.status_sequencia = ArtigoNormativo.StatusSequencia.DUPLICADO
            duplicados.setdefault(chave, [vistos[chave]]).append(artigo)
        else:
            vistos[chave] = artigo

    for (numero, sufixo), itens in duplicados.items():
        ocorrencias.append(
            OcorrenciaExtraida(
                categoria="segmentacao_artigo_duplicado",
                severidade=OcorrenciaDocumental.Severidade.ALTA,
                pagina=itens[0].pagina_inicial,
                descricao=f"O artigo {numero}{('-' + sufixo) if sufixo else ''} aparece mais de uma vez.",
                evidencias=[
                    {
                        "rotulo": item.rotulo,
                        "linha_inicial": item.linha_inicial,
                        "linha_final": item.linha_final,
                        "pagina_inicial": item.pagina_inicial,
                        "sha256_texto": sha256(item.texto.encode("utf-8")).hexdigest(),
                        "texto": item.texto,
                    }
                    for item in itens
                ],
            )
        )

    numeros_principais: list[int] = []
    for artigo in artigos:
        if artigo.sufixo or artigo.numero_normalizado in numeros_principais:
            continue
        numeros_principais.append(artigo.numero_normalizado)
    for anterior, atual in zip(numeros_principais, numeros_principais[1:], strict=False):
        if atual > anterior + 1:
            alvo = next(item for item in artigos if item.numero_normalizado == atual and not item.sufixo)
            alvo.status_sequencia = ArtigoNormativo.StatusSequencia.LACUNA
            ausentes = list(range(anterior + 1, atual))
            ocorrencias.append(
                OcorrenciaExtraida(
                    categoria="segmentacao_lacuna_sequencia",
                    severidade=OcorrenciaDocumental.Severidade.ALTA,
                    pagina=alvo.pagina_inicial,
                    descricao=f"Lacuna entre os artigos {anterior} e {atual}.",
                    evidencias=[{"artigos_ausentes": ausentes}],
                )
            )
        elif atual < anterior:
            ocorrencias.append(
                OcorrenciaExtraida(
                    categoria="segmentacao_ordem_irregular",
                    severidade=OcorrenciaDocumental.Severidade.ALTA,
                    descricao=f"O artigo {atual} aparece depois do artigo {anterior}.",
                )
            )

    inicio_primeira_unidade = marcadores[0][0] if marcadores else len(markdown)
    preambulo = markdown[:inicio_primeira_unidade].strip()
    caracteres_unidades = _uniao_intervalos(intervalos)
    caracteres_total = len(markdown)
    caracteres_atribuidos = caracteres_unidades + len(markdown[:inicio_primeira_unidade])
    caracteres_nao_atribuidos = max(caracteres_total - caracteres_atribuidos, 0)
    cobertura = (caracteres_atribuidos / caracteres_total * 100) if caracteres_total else 100.0
    percentual_nao_atribuido = (
        caracteres_nao_atribuidos / caracteres_total * 100 if caracteres_total else 0.0
    )

    metricas = {
        "artigos_detectados": len(artigos),
        "artigos_canonicos": len(vistos),
        "anexos_detectados": len(anexos),
        "ocorrencias_detectadas": len(ocorrencias),
        "duplicacoes_numeracao": len(duplicados),
        "lacunas_sequencia": sum(
            1 for item in ocorrencias if item.categoria == "segmentacao_lacuna_sequencia"
        ),
        "caracteres_total": caracteres_total,
        "caracteres_preambulo": len(preambulo),
        "caracteres_nao_atribuidos": caracteres_nao_atribuidos,
        "cobertura_percentual": round(cobertura, 4),
        "nao_atribuido_percentual": round(percentual_nao_atribuido, 4),
        "gate_cobertura_98": cobertura >= 98.0,
        "gate_nao_atribuido_2": percentual_nao_atribuido <= 2.0,
        "gate_sem_duplicacao": not duplicados,
    }
    return ResultadoSegmentacao(
        artigos=artigos,
        anexos=anexos,
        ocorrencias=ocorrencias,
        metricas=metricas,
        sha256_markdown=sha_markdown,
    )


def _artefato_markdown(versao: VersaoDocumento, artefato_id: int | None = None) -> ArtefatoProcessado:
    consulta = ArtefatoProcessado.objects.filter(
        processamento__versao_documento=versao,
        processamento__status=ProcessamentoDocumento.Status.CONCLUIDO,
        tipo=ArtefatoProcessado.Tipo.MARKDOWN,
    ).select_related("processamento")
    if artefato_id is not None:
        consulta = consulta.filter(pk=artefato_id)
    artefato = consulta.order_by("-criado_em", "-pk").first()
    if artefato is None:
        raise ErroSegmentacao("Nenhum artefato Markdown concluído foi localizado para a versão.")
    return artefato


def _ler_markdown(artefato: ArtefatoProcessado) -> str:
    try:
        with artefato.arquivo.open("rb") as arquivo:
            return arquivo.read().decode("utf-8", errors="replace")
    except OSError as erro:
        raise ErroSegmentacao(f"Não foi possível ler o Markdown: {erro}") from erro


def _natureza_ato(versao: VersaoDocumento) -> str:
    try:
        classificacao = versao.classificacao_normativa
    except (AttributeError, ObjectDoesNotExist):  # type: ignore[name-defined]
        return AtoNormativo.NaturezaTexto.NAO_IDENTIFICADA
    mapa = {
        "original_publicado": AtoNormativo.NaturezaTexto.ORIGINAL,
        "ato_modificador": AtoNormativo.NaturezaTexto.MODIFICADOR,
        "consolidacao_oficial": AtoNormativo.NaturezaTexto.CONSOLIDADO_OFICIAL,
        "compilacao_nao_oficial": AtoNormativo.NaturezaTexto.COMPILACAO,
    }
    return mapa.get(classificacao.natureza, AtoNormativo.NaturezaTexto.NAO_IDENTIFICADA)


def _identificador_ato(versao: VersaoDocumento) -> str:
    return f"versao-{versao.pk}-ato-principal"


def _identificador_artigo(versao: VersaoDocumento, artigo: ArtigoExtraido) -> str:
    sufixo = artigo.sufixo.lower() or "principal"
    return f"versao-{versao.pk}-art-{artigo.numero_normalizado}-{sufixo}"


def _identificador_anexo(versao: VersaoDocumento, indice: int) -> str:
    return f"versao-{versao.pk}-anexo-{indice:03d}"


def _possui_revisao_humana(versao: VersaoDocumento) -> bool:
    atos = versao.atos_normativos.filter(metadados__segmentacao_automatica=True)
    if atos.filter(status_auditoria=AtoNormativo.StatusAuditoria.APROVADO).exists():
        return True
    return ArtigoNormativo.objects.filter(
        ato__in=atos,
        status_auditoria__in=[
            ArtigoNormativo.StatusAuditoria.REVISADO,
            ArtigoNormativo.StatusAuditoria.ADJUDICADO,
        ],
    ).exists()


def _gravar_diagnostico(
    processamento: ProcessamentoDocumento,
    resultado: ResultadoSegmentacao,
) -> ArtefatoProcessado:
    conteudo = json.dumps(resultado.como_dict(), ensure_ascii=False, indent=2).encode("utf-8")
    artefato = ArtefatoProcessado(
        processamento=processamento,
        tipo=ArtefatoProcessado.Tipo.DIAGNOSTICO_JSON,
        sha256=sha256(conteudo).hexdigest(),
        tamanho_bytes=len(conteudo),
        mime_type="application/json",
        metadados={"schema": "segmentacao-unidades-normativas-0.4.1"},
    )
    artefato.arquivo.save(
        f"segmentacao-versao-{processamento.versao_documento_id}.json",
        ContentFile(conteudo),
        save=False,
    )
    artefato.save()
    return artefato


def executar_segmentacao(
    versao: VersaoDocumento,
    *,
    confirmar: bool = False,
    forcar: bool = False,
    substituir_revisados: bool = False,
    artefato_id: int | None = None,
) -> tuple[ResultadoSegmentacao, ProcessamentoDocumento | None, bool]:
    """Executa análise e, quando confirmada, persiste unidades de modo idempotente."""
    artefato = _artefato_markdown(versao, artefato_id)
    markdown = _ler_markdown(artefato)
    resultado = segmentar_markdown(markdown)
    parametros = {
        "artefato_markdown_id": artefato.pk,
        "sha256_markdown": artefato.sha256 or resultado.sha256_markdown,
        "versao_segmentador": VERSAO_SEGMENTADOR,
    }
    anterior = versao.processamentos.filter(
        etapa=ProcessamentoDocumento.Etapa.VALIDACAO,
        status=ProcessamentoDocumento.Status.CONCLUIDO,
        ferramenta=FERRAMENTA_SEGMENTADOR,
        versao_codigo=VERSAO_SEGMENTADOR,
        parametros=parametros,
    ).first()
    if anterior and not forcar:
        return resultado, anterior, True
    if not confirmar:
        return resultado, None, False
    if forcar and _possui_revisao_humana(versao) and not substituir_revisados:
        raise ErroSegmentacao(
            "Há unidades com revisão humana. Use --substituir-revisados somente após decisão explícita."
        )

    processamento = ProcessamentoDocumento.objects.create(
        versao_documento=versao,
        etapa=ProcessamentoDocumento.Etapa.VALIDACAO,
        status=ProcessamentoDocumento.Status.EM_EXECUCAO,
        rota_documento=artefato.processamento.rota_documento,
        ferramenta=FERRAMENTA_SEGMENTADOR,
        versao_ferramenta=VERSAO_SEGMENTADOR,
        versao_codigo=VERSAO_SEGMENTADOR,
        parametros=parametros,
        iniciado_em=timezone.now(),
    )
    inicio = monotonic()
    try:
        with transaction.atomic():
            versao.ocorrencias_documentais.filter(categoria__startswith=CATEGORIA_PREFIXO).delete()
            versao.atos_normativos.filter(metadados__segmentacao_automatica=True).delete()

            paginas = [item.pagina_final for item in resultado.artigos] + [
                item.pagina_final for item in resultado.anexos
            ]
            pagina_final = max(paginas, default=1)
            ato = AtoNormativo.objects.create(
                versao_documento=versao,
                identificador=_identificador_ato(versao),
                especie=versao.documento.tipo.nome,
                numero=versao.documento.numero,
                ano=versao.documento.ano,
                data_norma=versao.documento.data_publicacao,
                natureza_texto=_natureza_ato(versao),
                pagina_inicial=1,
                pagina_final=pagina_final,
                primeiro_artigo=resultado.artigos[0].numero_textual if resultado.artigos else "",
                ultimo_artigo=resultado.artigos[-1].numero_textual if resultado.artigos else "",
                status_auditoria=AtoNormativo.StatusAuditoria.EM_REVISAO,
                metadados={
                    "segmentacao_automatica": True,
                    "processamento_id": processamento.pk,
                    "artefato_markdown_id": artefato.pk,
                    "sha256_markdown": resultado.sha256_markdown,
                    "metricas": resultado.metricas,
                },
            )

            artigos_persistidos: dict[tuple[int, str], ArtigoNormativo] = {}
            for artigo in resultado.artigos:
                chave = (artigo.numero_normalizado, artigo.sufixo)
                if chave in artigos_persistidos:
                    continue
                registro = ArtigoNormativo.objects.create(
                    ato=ato,
                    identificador=_identificador_artigo(versao, artigo),
                    rotulo=artigo.rotulo,
                    numero_textual=artigo.numero_textual,
                    numero_normalizado=artigo.numero_normalizado,
                    sufixo=artigo.sufixo,
                    pagina_inicial=artigo.pagina_inicial,
                    pagina_final=artigo.pagina_final,
                    heading_encontrado=True,
                    texto=artigo.texto,
                    estrutura={
                        "segmentacao_automatica": True,
                        "inicio": artigo.inicio,
                        "fim": artigo.fim,
                        "linha_inicial": artigo.linha_inicial,
                        "linha_final": artigo.linha_final,
                        "sha256_markdown": resultado.sha256_markdown,
                    },
                    status_sequencia=artigo.status_sequencia,
                    status_auditoria=ArtigoNormativo.StatusAuditoria.AUTOMATICA,
                )
                artigos_persistidos[chave] = registro

            for indice, anexo in enumerate(resultado.anexos, start=1):
                AnexoNormativo.objects.create(
                    ato=ato,
                    identificador=_identificador_anexo(versao, indice),
                    titulo=anexo.titulo[:255],
                    tipo=anexo.tipo,
                    pagina_inicial=anexo.pagina_inicial,
                    pagina_final=anexo.pagina_final,
                    status=AnexoNormativo.Status.IDENTIFICADO,
                    metadados={
                        "segmentacao_automatica": True,
                        "inicio": anexo.inicio,
                        "fim": anexo.fim,
                        "linha_inicial": anexo.linha_inicial,
                        "linha_final": anexo.linha_final,
                        "texto": anexo.texto,
                        "sha256_texto": sha256(anexo.texto.encode("utf-8")).hexdigest(),
                    },
                )

            for ocorrencia in resultado.ocorrencias:
                artigo = None
                if ocorrencia.categoria == "segmentacao_artigo_duplicado" and ocorrencia.evidencias:
                    rotulo = ocorrencia.evidencias[0].get("rotulo", "")
                    artigo = next(
                        (item for item in artigos_persistidos.values() if item.rotulo == rotulo),
                        None,
                    )
                OcorrenciaDocumental.objects.create(
                    versao_documento=versao,
                    ato=ato,
                    artigo=artigo,
                    categoria=ocorrencia.categoria,
                    severidade=ocorrencia.severidade,
                    pagina=ocorrencia.pagina,
                    descricao=ocorrencia.descricao,
                    evidencias=ocorrencia.evidencias,
                )

            _gravar_diagnostico(processamento, resultado)
            processamento.metricas = resultado.metricas
            processamento.avisos = [item.descricao for item in resultado.ocorrencias]
            processamento.status = ProcessamentoDocumento.Status.CONCLUIDO
            processamento.concluido_em = timezone.now()
            processamento.duracao_segundos = monotonic() - inicio
            processamento.save()
        return resultado, processamento, False
    except Exception as erro:
        processamento.status = ProcessamentoDocumento.Status.FALHOU
        processamento.mensagem_erro = str(erro)
        processamento.concluido_em = timezone.now()
        processamento.duracao_segundos = monotonic() - inicio
        processamento.save()
        if isinstance(erro, ErroSegmentacao):
            raise
        raise ErroSegmentacao(str(erro)) from erro
