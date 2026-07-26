from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import VersaoDocumento


def calcular_sha256_com_fechamento(self: VersaoDocumento) -> str:
    """Calcula o hash e fecha somente o handle aberto internamente pelo FieldFile."""
    resumo = sha256()
    estava_fechado = self.arquivo.closed
    arquivo = self.arquivo.file

    try:
        posicao_original = arquivo.tell() if arquivo.seekable() else None
        arquivo.seek(0)

        if hasattr(arquivo, "chunks"):
            for bloco in arquivo.chunks():
                resumo.update(bloco)
        else:
            while bloco := arquivo.read(1024 * 1024):
                resumo.update(bloco)

        if posicao_original is not None:
            arquivo.seek(posicao_original)

        return resumo.hexdigest()
    finally:
        if estava_fechado:
            self.arquivo.close()


def aplicar_correcao_fieldfile() -> None:
    """Aplica a correção de portabilidade sem alterar handles fornecidos pelo chamador."""
    from .models import VersaoDocumento

    VersaoDocumento._calcular_sha256 = calcular_sha256_com_fechamento
