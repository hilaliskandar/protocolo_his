from __future__ import annotations

from pathlib import Path
from typing import ClassVar
from zipfile import is_zipfile

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import ImportacaoLote


def _nome_arquivo_seguro(nome: str) -> str:
    return Path(nome.replace("\\", "/")).name[:255]


class FormularioImportacaoLote(forms.ModelForm):
    inspecionar_apos_envio = forms.BooleanField(
        required=False,
        initial=True,
        label="Inspecionar o conteúdo após o envio",
        help_text=(
            "Executa a triagem dos PDFs imediatamente. A confirmação e a criação dos documentos "
            "continuam dependendo de revisão posterior."
        ),
    )

    class Meta:
        model = ImportacaoLote
        fields: ClassVar[list[str]] = [
            "titulo",
            "descricao",
            "origem_recebimento",
            "uf_padrao",
            "arquivo_zip",
        ]
        labels: ClassVar[dict[str, str]] = {
            "titulo": "Título do lote",
            "descricao": "Descrição",
            "origem_recebimento": "Origem do recebimento",
            "uf_padrao": "UF padrão",
            "arquivo_zip": "Arquivo ZIP",
        }
        help_texts: ClassVar[dict[str, str]] = {
            "arquivo_zip": "Envie um arquivo .zip contendo os PDFs do corpus normativo.",
            "uf_padrao": "Usada quando a UF não puder ser inferida da estrutura do lote.",
        }
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "uf_padrao": forms.TextInput(attrs={"maxlength": 2, "size": 4}),
            "arquivo_zip": forms.ClearableFileInput(attrs={"accept": ".zip,application/zip"}),
        }

    def clean_arquivo_zip(self):
        arquivo = self.cleaned_data["arquivo_zip"]
        if arquivo.size > settings.INGESTAO_MAX_ZIP_BYTES:
            limite_mb = settings.INGESTAO_MAX_ZIP_BYTES / (1024 * 1024)
            raise ValidationError(f"O ZIP excede o limite configurado de {limite_mb:.0f} MB.")
        if Path(arquivo.name).suffix.casefold() != ".zip":
            raise ValidationError("Selecione um arquivo com extensão .zip.")

        posicao = arquivo.tell()
        try:
            assinatura = arquivo.read(4)
            arquivo.seek(0)
            estrutura_valida = is_zipfile(arquivo)
        except (OSError, ValueError):
            estrutura_valida = False
            assinatura = b""
        finally:
            arquivo.seek(posicao)

        if assinatura[:2] != b"PK" or not estrutura_valida:
            raise ValidationError("O arquivo informado não possui uma estrutura ZIP válida.")
        return arquivo

    def save(self, commit: bool = True):
        lote = super().save(commit=False)
        lote.nome_original = _nome_arquivo_seguro(self.cleaned_data["arquivo_zip"].name)
        lote.parametros = {
            **(lote.parametros or {}),
            "origem_interface": True,
            "dry_run": True,
        }
        if commit:
            lote.save()
        return lote
