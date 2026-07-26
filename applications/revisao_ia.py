from __future__ import annotations

import difflib
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic
from typing import Any, Protocol

import httpx
from django.db import transaction
from django.utils import timezone
from prefect import flow, task
from pydantic import BaseModel, Field, ValidationError

from .conversao import _gravar_artefato
from .models import ArtefatoProcessado, ProcessamentoDocumento, VersaoDocumento

VERSAO_CODIGO_REVISAO = "revisao-ia-local-v1"
PROMPT_VERSAO = "revisao-fidelidade-normativa-v1"


class ErroRevisaoIALocal(RuntimeError):
    """Erro controlado durante a revisão assistida do Markdown."""


class AlteracaoProposta(BaseModel):
    tipo: str
    trecho_original: str = ""
    trecho_proposto: str = ""
    justificativa: str


class RespostaRevisao(BaseModel):
    status: str
    confianca: float = Field(ge=0, le=1)
    problemas: list[str] = Field(default_factory=list)
    texto_proposto: str
    alteracoes: list[AlteracaoProposta] = Field(default_factory=list)
    exige_validacao_humana: bool = False


class ClienteRevisao(Protocol):
    def revisar(self, *, unidade: str, texto: str) -> tuple[RespostaRevisao, dict[str, Any]]: ...


@dataclass(frozen=True)
class UnidadeMarkdown:
    identificador: str
    texto: str
    inicio: int
    fim: int


@dataclass(frozen=True)
class DecisaoGate:
    aprovada: bool
    motivos: tuple[str, ...]
    metricas: dict[str, Any]


PROTEGIDOS_RE = re.compile(
    r"(?ix)"
    r"(?:\b(?:art\.?|arts\.?|lei|decreto|resolu[cç][aã]o|n[ºo°])\s*[\w./-]+)"
    r"|(?:\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b)"
    r"|(?:\b\d+(?:[.,]\d+)?\s*%)"
    r"|(?:\bR\$\s*\d[\d.,]*)"
    r"|(?:§\s*\d+[ºo°]?)"
    r"|(?:\b\d+[ºo°]\b)"
)

CABECALHO_ARTIGO_RE = re.compile(
    r"(?im)^(?=#{1,6}\s+|\s*(?:art\.?|artigo)\s+\d+[\wº°-]*\b)"
)


def _hash_texto(texto: str) -> str:
    return sha256(texto.encode("utf-8")).hexdigest()


def _normalizar_protegido(valor: str) -> str:
    return re.sub(r"\s+", "", valor.casefold())


def _itens_protegidos(texto: str) -> list[str]:
    return [_normalizar_protegido(item) for item in PROTEGIDOS_RE.findall(texto)]


def segmentar_markdown(texto: str, *, max_caracteres: int = 8_000) -> list[UnidadeMarkdown]:
    """Segmenta por headings/artigos e subdivide blocos extensos sem perder posições."""
    if max_caracteres < 1_000:
        raise ValueError("max_caracteres deve ser pelo menos 1000.")
    inicios = sorted(set([0, *(m.start() for m in CABECALHO_ARTIGO_RE.finditer(texto))]))
    limites = [*inicios, len(texto)]
    unidades: list[UnidadeMarkdown] = []
    contador = 1
    for indice in range(len(limites) - 1):
        inicio, fim = limites[indice], limites[indice + 1]
        bloco = texto[inicio:fim]
        deslocamento = 0
        while len(bloco) - deslocamento > max_caracteres:
            corte_ideal = deslocamento + max_caracteres
            corte = texto.rfind("\n\n", inicio + deslocamento, inicio + corte_ideal)
            if corte <= inicio + deslocamento:
                corte = inicio + corte_ideal
            trecho = texto[inicio + deslocamento : corte]
            unidades.append(
                UnidadeMarkdown(f"unidade-{contador:05d}", trecho, inicio + deslocamento, corte)
            )
            contador += 1
            deslocamento = corte - inicio
        trecho = texto[inicio + deslocamento : fim]
        if trecho:
            unidades.append(
                UnidadeMarkdown(f"unidade-{contador:05d}", trecho, inicio + deslocamento, fim)
            )
            contador += 1
    return unidades


def avaliar_gates(
    original: str,
    proposto: str,
    resposta: RespostaRevisao,
    *,
    confianca_minima: float = 0.9,
    alteracao_maxima: float = 0.2,
    remocao_maxima: float = 0.08,
) -> DecisaoGate:
    motivos: list[str] = []
    similaridade = difflib.SequenceMatcher(None, original, proposto).ratio()
    taxa_alteracao = 1 - similaridade
    taxa_remocao = max(0, len(original) - len(proposto)) / max(1, len(original))
    protegidos_original = _itens_protegidos(original)
    protegidos_proposto = _itens_protegidos(proposto)
    preserva_protegidos = protegidos_original == protegidos_proposto

    if resposta.confianca < confianca_minima:
        motivos.append("confianca_abaixo_do_limite")
    if resposta.exige_validacao_humana:
        motivos.append("modelo_exigiu_validacao_humana")
    if taxa_alteracao > alteracao_maxima:
        motivos.append("alteracao_excessiva")
    if taxa_remocao > remocao_maxima:
        motivos.append("remocao_excessiva")
    if not preserva_protegidos:
        motivos.append("elementos_normativos_protegidos_alterados")
    if not proposto.strip():
        motivos.append("texto_proposto_vazio")

    return DecisaoGate(
        aprovada=not motivos,
        motivos=tuple(motivos),
        metricas={
            "similaridade": round(similaridade, 6),
            "taxa_alteracao": round(taxa_alteracao, 6),
            "taxa_remocao": round(taxa_remocao, 6),
            "elementos_protegidos_original": len(protegidos_original),
            "elementos_protegidos_proposto": len(protegidos_proposto),
            "preserva_elementos_protegidos": preserva_protegidos,
        },
    )


class ClienteOllama:
    def __init__(
        self,
        *,
        modelo: str,
        base_url: str | None = None,
        timeout: float = 180.0,
        temperatura: float = 0.0,
        seed: int = 42,
    ) -> None:
        self.modelo = modelo
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip(
            "/"
        )
        self.timeout = timeout
        self.temperatura = temperatura
        self.seed = seed

    @staticmethod
    def _prompt(unidade: str, texto: str) -> str:
        return f"""Você revisa conversões de legislação brasileira para Markdown.
Sua prioridade absoluta é fidelidade documental, não estilo.

REGRAS OBRIGATÓRIAS:
- não modernize, resuma, complete ou interprete a norma;
- não altere números, datas, percentuais, referências legais, artigos, parágrafos ou incisos;
- corrija apenas artefatos evidentes de OCR, hifenização, cabeçalho/rodapé e estrutura Markdown;
- em qualquer ambiguidade, preserve o texto e marque exige_validacao_humana=true;
- texto_proposto deve conter a unidade integral, mesmo sem alterações.

UNIDADE: {unidade}

TEXTO:
<<<
{texto}
>>>
"""

    def revisar(self, *, unidade: str, texto: str) -> tuple[RespostaRevisao, dict[str, Any]]:
        schema = RespostaRevisao.model_json_schema()
        payload = {
            "model": self.modelo,
            "stream": False,
            "format": schema,
            "messages": [{"role": "user", "content": self._prompt(unidade, texto)}],
            "options": {
                "temperature": self.temperatura,
                "seed": self.seed,
            },
        }
        inicio = monotonic()
        try:
            resposta_http = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            resposta_http.raise_for_status()
            dados = resposta_http.json()
            conteudo = dados["message"]["content"]
            resposta = RespostaRevisao.model_validate_json(conteudo)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError, ValidationError) as erro:
            raise ErroRevisaoIALocal(f"Resposta inválida do Ollama: {erro}") from erro
        uso = {
            "duracao_segundos": round(monotonic() - inicio, 6),
            "prompt_tokens": dados.get("prompt_eval_count"),
            "completion_tokens": dados.get("eval_count"),
            "total_duration_ns": dados.get("total_duration"),
            "load_duration_ns": dados.get("load_duration"),
            "prompt_eval_duration_ns": dados.get("prompt_eval_duration"),
            "eval_duration_ns": dados.get("eval_duration"),
            "done_reason": dados.get("done_reason"),
        }
        return resposta, uso


def _markdown_conversion_artifact(versao: VersaoDocumento) -> ArtefatoProcessado:
    artefato = (
        ArtefatoProcessado.objects.filter(
            processamento__versao_documento=versao,
            processamento__etapa=ProcessamentoDocumento.Etapa.CONVERSAO,
            processamento__status=ProcessamentoDocumento.Status.CONCLUIDO,
            tipo=ArtefatoProcessado.Tipo.MARKDOWN,
        )
        .select_related("processamento")
        .order_by("-criado_em", "-pk")
        .first()
    )
    if not artefato:
        raise ErroRevisaoIALocal("Não há Markdown convertido e concluído para esta versão.")
    return artefato


def _ler_markdown(artefato: ArtefatoProcessado) -> str:
    try:
        with artefato.arquivo.open("rb") as stream:
            return stream.read().decode("utf-8", errors="replace")
    except OSError as erro:
        raise ErroRevisaoIALocal(f"Não foi possível ler o Markdown: {erro}") from erro


def _somar_uso(registros: Iterable[dict[str, Any]]) -> dict[str, Any]:
    registros = list(registros)
    return {
        "chamadas": len(registros),
        "prompt_tokens": sum(item.get("prompt_tokens") or 0 for item in registros),
        "completion_tokens": sum(item.get("completion_tokens") or 0 for item in registros),
        "duracao_chamadas_segundos": round(
            sum(float(item.get("duracao_segundos") or 0) for item in registros), 6
        ),
    }


def revisar_markdown(
    texto: str,
    cliente: ClienteRevisao,
    *,
    max_caracteres: int = 8_000,
    confianca_minima: float = 0.9,
    alteracao_maxima: float = 0.2,
    remocao_maxima: float = 0.08,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    unidades = segmentar_markdown(texto, max_caracteres=max_caracteres)
    partes: list[str] = []
    registros: list[dict[str, Any]] = []
    usos: list[dict[str, Any]] = []

    for unidade in unidades:
        resposta, uso = cliente.revisar(unidade=unidade.identificador, texto=unidade.texto)
        gate = avaliar_gates(
            unidade.texto,
            resposta.texto_proposto,
            resposta,
            confianca_minima=confianca_minima,
            alteracao_maxima=alteracao_maxima,
            remocao_maxima=remocao_maxima,
        )
        texto_final = resposta.texto_proposto if gate.aprovada else unidade.texto
        partes.append(texto_final)
        usos.append(uso)
        registros.append(
            {
                "unidade": unidade.identificador,
                "inicio": unidade.inicio,
                "fim": unidade.fim,
                "sha256_original": _hash_texto(unidade.texto),
                "sha256_proposto": _hash_texto(resposta.texto_proposto),
                "sha256_aplicado": _hash_texto(texto_final),
                "status_modelo": resposta.status,
                "confianca": resposta.confianca,
                "problemas": resposta.problemas,
                "alteracoes": [item.model_dump() for item in resposta.alteracoes],
                "exige_validacao_humana": resposta.exige_validacao_humana,
                "gate_aprovado": gate.aprovada,
                "motivos_gate": list(gate.motivos),
                "metricas_gate": gate.metricas,
                "uso": uso,
            }
        )

    revisado = "".join(partes)
    aprovadas = sum(1 for item in registros if item["gate_aprovado"])
    alteradas = sum(
        1
        for item in registros
        if item["sha256_original"] != item["sha256_proposto"]
    )
    metricas = {
        "unidades_total": len(registros),
        "unidades_com_proposta": alteradas,
        "unidades_autoaprovadas": aprovadas,
        "unidades_bloqueadas": len(registros) - aprovadas,
        "taxa_autoaprovacao": round(aprovadas / max(1, len(registros)), 6),
        "caracteres_original": len(texto),
        "caracteres_revisado": len(revisado),
        "sha256_original_markdown": _hash_texto(texto),
        "sha256_revisado_markdown": _hash_texto(revisado),
        "uso_ia": _somar_uso(usos),
    }
    return revisado, registros, metricas


def executar_revisao_versao(
    versao: VersaoDocumento,
    *,
    modelo: str,
    forcar: bool = False,
    cliente: ClienteRevisao | None = None,
    max_caracteres: int = 8_000,
    confianca_minima: float = 0.9,
    alteracao_maxima: float = 0.2,
    remocao_maxima: float = 0.08,
) -> ProcessamentoDocumento:
    origem = _markdown_conversion_artifact(versao)
    parametros = {
        "modelo": modelo,
        "prompt_versao": PROMPT_VERSAO,
        "artefato_origem_id": origem.pk,
        "sha256_markdown_origem": origem.sha256,
        "max_caracteres": max_caracteres,
        "confianca_minima": confianca_minima,
        "alteracao_maxima": alteracao_maxima,
        "remocao_maxima": remocao_maxima,
    }
    anterior = versao.processamentos.filter(
        etapa=ProcessamentoDocumento.Etapa.VALIDACAO,
        status=ProcessamentoDocumento.Status.CONCLUIDO,
        ferramenta="ollama-revisao-markdown",
        versao_codigo=VERSAO_CODIGO_REVISAO,
        parametros=parametros,
    ).first()
    if anterior and not forcar:
        return anterior

    processamento = ProcessamentoDocumento.objects.create(
        versao_documento=versao,
        etapa=ProcessamentoDocumento.Etapa.VALIDACAO,
        status=ProcessamentoDocumento.Status.EM_EXECUCAO,
        rota_documento=origem.processamento.rota_documento,
        ferramenta="ollama-revisao-markdown",
        versao_ferramenta=modelo,
        versao_codigo=VERSAO_CODIGO_REVISAO,
        parametros=parametros,
        iniciado_em=timezone.now(),
    )
    inicio = monotonic()
    cliente = cliente or ClienteOllama(modelo=modelo)

    try:
        original = _ler_markdown(origem)
        revisado, registros, metricas = revisar_markdown(
            original,
            cliente,
            max_caracteres=max_caracteres,
            confianca_minima=confianca_minima,
            alteracao_maxima=alteracao_maxima,
            remocao_maxima=remocao_maxima,
        )
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                revisado.splitlines(keepends=True),
                fromfile=f"origem-{origem.sha256}.md",
                tofile="revisado-candidato.md",
            )
        )
        jsonl = "\n".join(json.dumps(item, ensure_ascii=False) for item in registros) + "\n"
        metricas.update(
            {
                "artefato_origem_id": origem.pk,
                "modelo": modelo,
                "prompt_versao": PROMPT_VERSAO,
                "diff_linhas": len(diff.splitlines()),
            }
        )

        with transaction.atomic():
            _gravar_artefato(
                processamento,
                tipo=ArtefatoProcessado.Tipo.MARKDOWN,
                nome="documento-revisado-candidato.md",
                conteudo=revisado.encode("utf-8"),
                mime_type="text/markdown",
                metadados={
                    "papel": "candidato_revisado",
                    "artefato_origem_id": origem.pk,
                    "sha256_origem": origem.sha256,
                    "aplicacao_automatica": "somente_unidades_aprovadas_pelos_gates",
                },
            )
            _gravar_artefato(
                processamento,
                tipo=ArtefatoProcessado.Tipo.DIAGNOSTICO_JSON,
                nome="revisao-ia.jsonl",
                conteudo=jsonl.encode("utf-8"),
                mime_type="application/x-ndjson",
                metadados={"schema": "revisao-ia-local-v1", "unidades": len(registros)},
            )
            _gravar_artefato(
                processamento,
                tipo=ArtefatoProcessado.Tipo.LOG,
                nome="diferencas-revisao.diff",
                conteudo=diff.encode("utf-8"),
                mime_type="text/x-diff",
                metadados={"sha256_origem": origem.sha256},
            )
            processamento.metricas = metricas
            processamento.avisos = [
                f"{metricas['unidades_bloqueadas']} unidade(s) dependem de validação humana."
            ] if metricas["unidades_bloqueadas"] else []
            processamento.status = ProcessamentoDocumento.Status.CONCLUIDO
            processamento.concluido_em = timezone.now()
            processamento.duracao_segundos = monotonic() - inicio
            processamento.save()
        return processamento
    except Exception as erro:
        processamento.status = ProcessamentoDocumento.Status.FALHOU
        processamento.mensagem_erro = str(erro)
        processamento.concluido_em = timezone.now()
        processamento.duracao_segundos = monotonic() - inicio
        processamento.save()
        if isinstance(erro, ErroRevisaoIALocal):
            raise
        raise ErroRevisaoIALocal(str(erro)) from erro


@task(retries=1, retry_delay_seconds=5)
def tarefa_revisar_versao(versao_id: int, configuracao: dict[str, Any]) -> int:
    versao = VersaoDocumento.objects.get(pk=versao_id)
    processamento = executar_revisao_versao(versao, **configuracao)
    return processamento.pk


@flow(name="revisao-qualidade-ia-local")
def fluxo_revisar_versoes(
    versoes_ids: list[int],
    *,
    modelo: str,
    forcar: bool = False,
    max_caracteres: int = 8_000,
    confianca_minima: float = 0.9,
    alteracao_maxima: float = 0.2,
    remocao_maxima: float = 0.08,
) -> list[int]:
    configuracao = {
        "modelo": modelo,
        "forcar": forcar,
        "max_caracteres": max_caracteres,
        "confianca_minima": confianca_minima,
        "alteracao_maxima": alteracao_maxima,
        "remocao_maxima": remocao_maxima,
    }
    return [tarefa_revisar_versao(versao_id, configuracao) for versao_id in versoes_ids]
