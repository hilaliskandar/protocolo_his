from __future__ import annotations

from pathlib import Path

INICIO = "<!-- INICIO: APENDICE-DECISOES-TECNOLOGICAS -->"
FIM = "<!-- FIM: APENDICE-DECISOES-TECNOLOGICAS -->"
ANCORA = "## Licença e contribuição"

raiz = Path(__file__).resolve().parents[1]
readme_path = raiz / "README.md"
fonte_path = raiz / "docs" / "decisoes-tecnologicas.md"

readme = readme_path.read_text(encoding="utf-8")
fonte = fonte_path.read_text(encoding="utf-8").strip()

if fonte.startswith("# "):
    fonte = "## " + fonte[2:]

bloco = f"{INICIO}\n\n{fonte}\n\n{FIM}"

if INICIO in readme and FIM in readme:
    prefixo, restante = readme.split(INICIO, 1)
    _, sufixo = restante.split(FIM, 1)
    atualizado = f"{prefixo}{bloco}{sufixo}"
elif ANCORA in readme:
    atualizado = readme.replace(ANCORA, f"{bloco}\n\n---\n\n{ANCORA}", 1)
else:
    atualizado = f"{readme.rstrip()}\n\n---\n\n{bloco}\n"

if atualizado != readme:
    readme_path.write_text(atualizado, encoding="utf-8")
