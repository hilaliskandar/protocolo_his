from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Apendice:
    fonte: str
    inicio: str
    fim: str
    ancora: str | None = None


APENDICES = (
    Apendice(
        fonte="docs/decisoes-tecnologicas.md",
        inicio="<!-- INICIO: APENDICE-DECISOES-TECNOLOGICAS -->",
        fim="<!-- FIM: APENDICE-DECISOES-TECNOLOGICAS -->",
        ancora="## Licença e contribuição",
    ),
    Apendice(
        fonte="docs/APENDICE_VERSIONAMENTO.md",
        inicio="<!-- INICIO: APENDICE-VERSIONAMENTO -->",
        fim="<!-- FIM: APENDICE-VERSIONAMENTO -->",
    ),
)


def _normalizar_fonte(conteudo: str) -> str:
    fonte = conteudo.strip()
    if fonte.startswith("# "):
        fonte = "## " + fonte[2:]
    return fonte


def _sincronizar_bloco(readme: str, fonte: str, apendice: Apendice) -> str:
    bloco = f"{apendice.inicio}\n\n{fonte}\n\n{apendice.fim}"
    if apendice.inicio in readme and apendice.fim in readme:
        prefixo, restante = readme.split(apendice.inicio, 1)
        _, sufixo = restante.split(apendice.fim, 1)
        return f"{prefixo}{bloco}{sufixo}"
    if apendice.ancora and apendice.ancora in readme:
        return readme.replace(
            apendice.ancora,
            f"{bloco}\n\n---\n\n{apendice.ancora}",
            1,
        )
    return f"{readme.rstrip()}\n\n---\n\n{bloco}\n"


def sincronizar() -> bool:
    raiz = Path(__file__).resolve().parents[1]
    readme_path = raiz / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    atualizado = readme

    for apendice in APENDICES:
        fonte = _normalizar_fonte((raiz / apendice.fonte).read_text(encoding="utf-8"))
        atualizado = _sincronizar_bloco(atualizado, fonte, apendice)

    if atualizado == readme:
        return False
    readme_path.write_text(atualizado, encoding="utf-8")
    return True


if __name__ == "__main__":
    print("README atualizado." if sincronizar() else "README já está sincronizado.")
