from __future__ import annotations

import re
from dataclasses import dataclass, field

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from applications.models import (
    AnexoNormativo,
    ArtefatoProcessado,
    ArtigoNormativo,
    AtoNormativo,
    ProcessamentoDocumento,
    VersaoDocumento,
)


PAGE_RE = re.compile(r"^(?:#+\s*)?(?:p[aá]gina|pagina|page)\s+(\d+)\b", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ANEXO_RE = re.compile(r"^(anexo|quadro|tabela|mapa|formul[aá]rio|coordenadas?)\b", re.IGNORECASE)
ARTIGO_RE = re.compile(
    r"^(?:#+\s*)?(Art\.?|Artigo)\s+"
    r"(\d+(?:[A-Za-z](?=\b|[-/]))?(?:[-/][A-Za-z0-9]+)?)(.*)$"
)
ATO_RE = re.compile(
    r"\b("
    r"lei complementar|lei ordin[aá]ria|lei delegada|lei|decreto legislativo|decreto|"
    r"portaria|resolu[cç][aã]o|instru[cç][aã]o normativa|emenda|medida provis[oó]ria|"
    r"plano diretor|c[oó]digo"
    r")\b(?:\s+n[.º°o]?\s*|\s+)?([0-9A-Za-z./-]+)?(?:\s*/\s*(\d{4}))?",
    re.IGNORECASE,
)


@dataclass
class CandidatoAnexo:
    titulo: str
    identificador: str
    tipo: str
    pagina_inicial: int
    pagina_final: int


@dataclass
class CandidatoArtigo:
    identificador: str
    rotulo: str
    numero_textual: str
    numero_normalizado: int | None
    sufixo: str
    pagina_inicial: int
    pagina_final: int
    heading_encontrado: bool
    fonte_pos_bloco: bool
    texto_linhas: list[str] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return "\n".join(linha.rstrip() for linha in self.texto_linhas).strip()


@dataclass
class CandidatoAto:
    titulo: str
    identificador: str
    especie: str
    numero: str
    ano: int | None
    pagina_inicial: int
    pagina_final: int
    ementa: str = ""
    primeiro_artigo: str = ""
    ultimo_artigo: str = ""
    artigos: list[CandidatoArtigo] = field(default_factory=list)
    anexos: list[CandidatoAnexo] = field(default_factory=list)
    implicito: bool = False


def _pagina_padrao(valor: int | None) -> int:
    return valor or 1


def _identificador_base(versao: VersaoDocumento) -> str:
    municipio = slugify(versao.documento.aplicacao.municipio.nome) or "municipio"
    return f"vd-{versao.pk}-{municipio}"


def _normalizar_titulo(texto: str) -> str:
    return " ".join(texto.replace("*", " ").strip().split())


def _extrair_heading(linha: str) -> tuple[int, str] | None:
    correspondencia = HEADING_RE.match(linha.strip())
    if not correspondencia:
        return None
    return len(correspondencia.group(1)), _normalizar_titulo(correspondencia.group(2))


def _extrair_pagina(linha: str) -> int | None:
    correspondencia = PAGE_RE.match(linha.strip())
    if not correspondencia:
        return None
    return int(correspondencia.group(1))


def _extrair_especie_numero_ano(
    texto: str,
    versao: VersaoDocumento,
    *,
    usar_documento_como_fallback: bool,
) -> tuple[str, str, int | None]:
    correspondencia = ATO_RE.search(texto)
    if correspondencia:
        especie = correspondencia.group(1).strip().title()
        numero = (correspondencia.group(2) or "").strip(" .-")
        ano = correspondencia.group(3)
        return especie, numero, int(ano) if ano else None
    if usar_documento_como_fallback:
        return (
            versao.documento.tipo.nome,
            versao.documento.numero,
            versao.documento.ano,
        )
    return "", "", None


def _identificador_ato(versao: VersaoDocumento, titulo: str, pagina: int) -> str:
    base = slugify(titulo) or "ato"
    return f"{_identificador_base(versao)}-ato-p{pagina:04d}-{base}"[:180]


def _identificador_artigo(ato: CandidatoAto, rotulo: str, pagina: int) -> str:
    base = slugify(rotulo) or f"art-p{pagina:04d}"
    return f"{ato.identificador}-{base}"[:220]


def _identificador_anexo(ato: CandidatoAto, titulo: str, pagina: int) -> str:
    base = slugify(titulo) or f"anexo-p{pagina:04d}"
    return f"{ato.identificador}-{base}"[:220]


def _tipo_anexo_por_titulo(titulo: str) -> str:
    valor = titulo.casefold()
    if valor.startswith(("quadro", "tabela")) or " quadro" in valor or " tabela" in valor:
        return AnexoNormativo.Tipo.TABELA
    if valor.startswith("mapa"):
        return AnexoNormativo.Tipo.MAPA
    if valor.startswith("formul"):
        return AnexoNormativo.Tipo.FORMULARIO
    if valor.startswith("coordenad"):
        return AnexoNormativo.Tipo.COORDENADAS
    if valor.startswith("anexo"):
        return AnexoNormativo.Tipo.TEXTO
    return AnexoNormativo.Tipo.OUTRO


def _extrair_dados_artigo(linha: str) -> tuple[str, str, int | None, str, str] | None:
    correspondencia = ARTIGO_RE.match(linha.strip())
    if not correspondencia:
        return None
    prefixo, numero_bruto, restante = correspondencia.groups()
    numero_bruto = numero_bruto.strip()
    numero_normalizado = None
    sufixo = ""
    numero_textual = numero_bruto
    numero_match = re.match(r"^(\d+)(?:[-/]?([A-Za-z0-9]+))?$", numero_bruto)
    if numero_match:
        numero_normalizado = int(numero_match.group(1))
        sufixo = (numero_match.group(2) or "").upper()
    restante = restante.lstrip()
    ordinal = ""
    if restante:
        primeiro = restante[0]
        if primeiro in {"º", "°", "ª"}:
            ordinal = primeiro
            restante = restante[1:].lstrip()
        elif primeiro in {"o", "O", "a", "A"} and (len(restante) == 1 or not restante[1].isalnum()):
            ordinal = primeiro
            restante = restante[1:].lstrip()
    rotulo = f"{prefixo} {numero_bruto}{ordinal}".strip()
    return rotulo, numero_textual, numero_normalizado, sufixo, restante.strip()


def _eh_heading_ato(texto: str, nivel: int, possui_ato_atual: bool) -> bool:
    if nivel > 2:
        return False
    if not possui_ato_atual:
        return True
    return bool(ATO_RE.search(texto))


def _garantir_ato(
    atos: list[CandidatoAto],
    versao: VersaoDocumento,
    pagina_atual: int | None,
) -> CandidatoAto:
    if atos:
        return atos[-1]
    pagina = _pagina_padrao(pagina_atual)
    especie, numero, ano = _extrair_especie_numero_ano(
        versao.documento.titulo,
        versao,
        usar_documento_como_fallback=True,
    )
    ato = CandidatoAto(
        titulo=versao.documento.titulo,
        identificador=_identificador_ato(versao, versao.documento.titulo, pagina),
        especie=especie,
        numero=numero,
        ano=ano,
        ementa=versao.documento.titulo,
        pagina_inicial=pagina,
        pagina_final=pagina,
        implicito=True,
    )
    atos.append(ato)
    return ato


def _parsear_markdown(markdown: str, versao: VersaoDocumento) -> list[CandidatoAto]:
    atos: list[CandidatoAto] = []
    pagina_atual: int | None = None
    artigo_atual: CandidatoArtigo | None = None
    anexo_atual: CandidatoAnexo | None = None

    def atualizar_intervalos() -> None:
        pagina = _pagina_padrao(pagina_atual)
        if atos:
            atos[-1].pagina_final = max(atos[-1].pagina_final, pagina)
        if artigo_atual is not None:
            artigo_atual.pagina_final = max(artigo_atual.pagina_final, pagina)
        if anexo_atual is not None:
            anexo_atual.pagina_final = max(anexo_atual.pagina_final, pagina)

    def fechar_artigo() -> None:
        nonlocal artigo_atual
        if artigo_atual is None or not atos:
            artigo_atual = None
            return
        if not artigo_atual.texto:
            artigo_atual = None
            return
        atos[-1].artigos.append(artigo_atual)
        if not atos[-1].primeiro_artigo:
            atos[-1].primeiro_artigo = artigo_atual.rotulo
        atos[-1].ultimo_artigo = artigo_atual.rotulo
        artigo_atual = None

    def fechar_anexo() -> None:
        nonlocal anexo_atual
        if anexo_atual is None or not atos:
            anexo_atual = None
            return
        atos[-1].anexos.append(anexo_atual)
        anexo_atual = None

    for linha in markdown.splitlines():
        pagina = _extrair_pagina(linha)
        if pagina is not None:
            pagina_atual = pagina
            atualizar_intervalos()
            continue

        atualizar_intervalos()
        heading = _extrair_heading(linha)
        conteudo = _normalizar_titulo(linha)

        if heading is not None:
            nivel, texto_heading = heading
            pagina_heading = _extrair_pagina(texto_heading)
            if pagina_heading is not None:
                pagina_atual = pagina_heading
                atualizar_intervalos()
                continue
            if ANEXO_RE.match(texto_heading):
                fechar_artigo()
                fechar_anexo()
                ato = _garantir_ato(atos, versao, pagina_atual)
                pagina = _pagina_padrao(pagina_atual)
                anexo_atual = CandidatoAnexo(
                    titulo=texto_heading,
                    identificador=_identificador_anexo(ato, texto_heading, pagina),
                    tipo=_tipo_anexo_por_titulo(texto_heading),
                    pagina_inicial=pagina,
                    pagina_final=pagina,
                )
                continue
            dados_artigo = _extrair_dados_artigo(texto_heading)
            if dados_artigo:
                fechar_artigo()
                fechar_anexo()
                ato = _garantir_ato(atos, versao, pagina_atual)
                rotulo, numero_textual, numero_normalizado, sufixo, restante = dados_artigo
                pagina = _pagina_padrao(pagina_atual)
                artigo_atual = CandidatoArtigo(
                    identificador=_identificador_artigo(ato, rotulo, pagina),
                    rotulo=rotulo,
                    numero_textual=numero_textual,
                    numero_normalizado=numero_normalizado,
                    sufixo=sufixo,
                    pagina_inicial=pagina,
                    pagina_final=pagina,
                    heading_encontrado=True,
                    fonte_pos_bloco=False,
                    texto_linhas=[restante] if restante else [],
                )
                continue
            if _eh_heading_ato(texto_heading, nivel, bool(atos)):
                fechar_artigo()
                fechar_anexo()
                pagina = _pagina_padrao(pagina_atual)
                usar_fallback = not atos and slugify(texto_heading) == slugify(versao.documento.titulo)
                especie, numero, ano = _extrair_especie_numero_ano(
                    texto_heading,
                    versao,
                    usar_documento_como_fallback=usar_fallback,
                )
                atos.append(
                    CandidatoAto(
                        titulo=texto_heading,
                        identificador=_identificador_ato(versao, texto_heading, pagina),
                        especie=especie,
                        numero=numero,
                        ano=ano,
                        ementa=texto_heading,
                        pagina_inicial=pagina,
                        pagina_final=pagina,
                    )
                )
                continue

        dados_artigo = _extrair_dados_artigo(conteudo)
        if dados_artigo:
            fechar_artigo()
            fechar_anexo()
            ato = _garantir_ato(atos, versao, pagina_atual)
            rotulo, numero_textual, numero_normalizado, sufixo, restante = dados_artigo
            pagina = _pagina_padrao(pagina_atual)
            artigo_atual = CandidatoArtigo(
                identificador=_identificador_artigo(ato, rotulo, pagina),
                rotulo=rotulo,
                numero_textual=numero_textual,
                numero_normalizado=numero_normalizado,
                sufixo=sufixo,
                pagina_inicial=pagina,
                pagina_final=pagina,
                heading_encontrado=False,
                fonte_pos_bloco=True,
                texto_linhas=[restante] if restante else [],
            )
            continue

        if artigo_atual is not None:
            artigo_atual.texto_linhas.append(linha.rstrip())

    fechar_artigo()
    fechar_anexo()
    return atos


class Command(BaseCommand):
    help = "Importa atos, artigos e anexos a partir do artefato Markdown convertido."

    def add_arguments(self, parser) -> None:
        parser.add_argument("versao_documento_pk", type=int)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opcoes) -> None:
        try:
            versao = VersaoDocumento.objects.select_related(
                "documento",
                "documento__tipo",
                "documento__aplicacao",
                "documento__aplicacao__municipio",
            ).get(pk=opcoes["versao_documento_pk"])
        except VersaoDocumento.DoesNotExist as erro:
            raise CommandError("A versão documental informada não existe.") from erro

        artefato = (
            ArtefatoProcessado.objects.select_related("processamento")
            .filter(
                processamento__versao_documento=versao,
                processamento__status=ProcessamentoDocumento.Status.CONCLUIDO,
                tipo=ArtefatoProcessado.Tipo.MARKDOWN,
            )
            .order_by("-processamento__concluido_em", "-processamento_id", "-pk")
            .first()
        )
        if artefato is None:
            raise CommandError("Nenhum artefato Markdown concluído foi encontrado para a versão.")

        artefato.arquivo.open("rb")
        try:
            markdown = artefato.arquivo.read().decode("utf-8")
        finally:
            artefato.arquivo.close()

        atos = _parsear_markdown(markdown, versao)
        if not atos:
            self.stderr.write(
                self.style.WARNING("Nenhum ato normativo foi identificado no Markdown informado.")
            )
            return

        contagem = {
            "atos_criados": 0,
            "atos_ignorados": 0,
            "artigos_criados": 0,
            "artigos_ignorados": 0,
            "anexos_criados": 0,
            "anexos_ignorados": 0,
        }
        detalhes: list[str] = []

        def importar() -> None:
            for candidato_ato in atos:
                ato, criado_ato = AtoNormativo.objects.get_or_create(
                    identificador=candidato_ato.identificador,
                    defaults={
                        "versao_documento": versao,
                        "especie": candidato_ato.especie,
                        "numero": candidato_ato.numero,
                        "ano": candidato_ato.ano,
                        "ementa": candidato_ato.ementa,
                        "pagina_inicial": candidato_ato.pagina_inicial,
                        "pagina_final": candidato_ato.pagina_final,
                        "primeiro_artigo": candidato_ato.primeiro_artigo,
                        "ultimo_artigo": candidato_ato.ultimo_artigo,
                        "metadados": {
                            "artefato_markdown_id": artefato.pk,
                            "titulo_extraido": candidato_ato.titulo,
                            "origem": "importar_atos_markdown",
                            "ato_implicito": candidato_ato.implicito,
                        },
                    },
                )
                contagem["atos_criados" if criado_ato else "atos_ignorados"] += 1
                if opcoes["verbosity"] >= 2:
                    detalhes.append(
                        f"Ato {'criado' if criado_ato else 'ignorado'}: {candidato_ato.identificador}"
                    )

                for candidato_artigo in candidato_ato.artigos:
                    artigo_existente = ArtigoNormativo.objects.filter(
                        ato=ato,
                        numero_textual=candidato_artigo.numero_textual,
                        sufixo=candidato_artigo.sufixo,
                    ).first()
                    if artigo_existente is not None:
                        contagem["artigos_ignorados"] += 1
                        if opcoes["verbosity"] >= 2:
                            detalhes.append(f"Artigo ignorado: {artigo_existente.identificador}")
                        continue
                    artigo, criado_artigo = ArtigoNormativo.objects.get_or_create(
                        identificador=candidato_artigo.identificador,
                        defaults={
                            "ato": ato,
                            "rotulo": candidato_artigo.rotulo,
                            "numero_textual": candidato_artigo.numero_textual,
                            "numero_normalizado": candidato_artigo.numero_normalizado,
                            "sufixo": candidato_artigo.sufixo,
                            "pagina_inicial": candidato_artigo.pagina_inicial,
                            "pagina_final": candidato_artigo.pagina_final,
                            "heading_encontrado": candidato_artigo.heading_encontrado,
                            "fonte_pos_bloco": candidato_artigo.fonte_pos_bloco,
                            "texto": candidato_artigo.texto,
                            "estrutura": {
                                "artefato_markdown_id": artefato.pk,
                                "origem": "importar_atos_markdown",
                            },
                        },
                    )
                    contagem["artigos_criados" if criado_artigo else "artigos_ignorados"] += 1
                    if opcoes["verbosity"] >= 2:
                        detalhes.append(
                            f"Artigo {'criado' if criado_artigo else 'ignorado'}: "
                            f"{candidato_artigo.identificador}"
                        )

                for candidato_anexo in candidato_ato.anexos:
                    anexo, criado_anexo = AnexoNormativo.objects.get_or_create(
                        identificador=candidato_anexo.identificador,
                        defaults={
                            "ato": ato,
                            "titulo": candidato_anexo.titulo,
                            "tipo": candidato_anexo.tipo,
                            "pagina_inicial": candidato_anexo.pagina_inicial,
                            "pagina_final": candidato_anexo.pagina_final,
                            "metadados": {
                                "artefato_markdown_id": artefato.pk,
                                "origem": "importar_atos_markdown",
                            },
                        },
                    )
                    contagem["anexos_criados" if criado_anexo else "anexos_ignorados"] += 1
                    if opcoes["verbosity"] >= 2:
                        detalhes.append(
                            f"Anexo {'criado' if criado_anexo else 'ignorado'}: "
                            f"{candidato_anexo.identificador}"
                        )

        if opcoes["dry_run"]:
            with transaction.atomic():
                importar()
                transaction.set_rollback(True)
        else:
            with transaction.atomic():
                importar()

        for detalhe in detalhes:
            self.stdout.write(detalhe)

        resumo = (
            f"Importação encerrada{' (dry-run)' if opcoes['dry_run'] else ''}: "
            f"{contagem['atos_criados']} ato(s) criado(s), {contagem['atos_ignorados']} ignorado(s); "
            f"{contagem['artigos_criados']} artigo(s) criado(s), "
            f"{contagem['artigos_ignorados']} ignorado(s); "
            f"{contagem['anexos_criados']} anexo(s) criado(s), "
            f"{contagem['anexos_ignorados']} ignorado(s)."
        )
        estilo = self.style.WARNING if opcoes["dry_run"] else self.style.SUCCESS
        self.stdout.write(estilo(resumo))
