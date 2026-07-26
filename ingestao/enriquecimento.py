from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

RE_ATO_TEXTO = re.compile(
    r"\b(?:lei\s+complementar|lei\s+ordin[aá]ria|lei|lc)\s*"
    r"(?:n[º°o.]*)?\s*([0-9][0-9.\-/]*)"
    r"(?:\s*,?\s*(?:de|/|-)\s*(?:\d{1,2}\s+de\s+\w+\s+de\s+)?)?"
    r"(18\d{2}|19\d{2}|20\d{2}|21\d{2}|22\d{2})?",
    re.IGNORECASE,
)
RE_ANO = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2}|22\d{2})\b")


def normalizar_numero(valor: str) -> str:
    """Produz chave canônica numérica sem apagar a forma original exibida."""
    return "".join(caractere for caractere in valor if caractere.isdigit())


@dataclass(frozen=True)
class DiagnosticoPreliminar:
    paginas: int
    paginas_amostradas: int
    caracteres_amostra: int
    rota_sugerida: str
    texto_amostra: str
    numero_texto: str
    ano_texto: int | None
    avisos: list[str]


def _metadados_do_texto(texto: str) -> tuple[str, int | None]:
    achado = RE_ATO_TEXTO.search(texto)
    if not achado:
        return "", None
    numero = achado.group(1).strip(" .-/")
    ano = int(achado.group(2)) if achado.group(2) else None
    if ano is None:
        trecho = texto[achado.end() : achado.end() + 180]
        ano_achado = RE_ANO.search(trecho)
        ano = int(ano_achado.group(1)) if ano_achado else None
    return numero, ano


def diagnosticar_pdf(caminho: str | Path, limite_paginas: int = 3) -> DiagnosticoPreliminar:
    avisos: list[str] = []
    try:
        leitor = PdfReader(str(caminho), strict=False)
        total_paginas = len(leitor.pages)
        textos: list[str] = []
        paginas_amostradas = min(total_paginas, limite_paginas)
        for pagina in leitor.pages[:paginas_amostradas]:
            try:
                textos.append(pagina.extract_text() or "")
            except Exception as erro:  # pypdf pode falhar isoladamente em uma página malformada
                textos.append("")
                avisos.append(f"extração preliminar falhou em uma página: {erro}")
        texto = "\n".join(textos)
        caracteres = len(texto.strip())
        media = caracteres / max(paginas_amostradas, 1)
        if caracteres == 0:
            rota = "ocr"
            avisos.append("nenhum texto nativo encontrado na amostra; OCR provavelmente necessário")
        elif media < 200:
            rota = "misto"
            avisos.append("pouco texto nativo na amostra; verificar páginas escaneadas")
        else:
            rota = "texto_nativo"
        numero, ano = _metadados_do_texto(texto)
        return DiagnosticoPreliminar(
            paginas=total_paginas,
            paginas_amostradas=paginas_amostradas,
            caracteres_amostra=caracteres,
            rota_sugerida=rota,
            texto_amostra=re.sub(r"\s+", " ", texto).strip()[:4000],
            numero_texto=numero,
            ano_texto=ano,
            avisos=avisos,
        )
    except Exception as erro:
        return DiagnosticoPreliminar(
            paginas=0,
            paginas_amostradas=0,
            caracteres_amostra=0,
            rota_sugerida="manual",
            texto_amostra="",
            numero_texto="",
            ano_texto=None,
            avisos=[f"diagnóstico preliminar do PDF falhou: {erro}"],
        )
