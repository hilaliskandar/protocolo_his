from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from applications.models import VersaoDocumento
from applications.segmentacao import ErroSegmentacao, executar_segmentacao


class Command(BaseCommand):
    help = "Segmenta deterministicamente artigos e anexos de um Markdown convertido."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--versao", type=int, required=True, help="ID da versão documental.")
        parser.add_argument("--artefato", type=int, help="ID explícito do artefato Markdown.")
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Persiste ato, artigos, anexos, ocorrências e processamento.",
        )
        parser.add_argument(
            "--forcar",
            action="store_true",
            help="Reexecuta mesmo quando a mesma entrada já foi concluída.",
        )
        parser.add_argument(
            "--substituir-revisados",
            action="store_true",
            help="Autoriza substituir unidades que já receberam revisão humana.",
        )
        parser.add_argument("--saida-json", type=Path, help="Grava o diagnóstico em JSON.")

    def handle(self, *args, **opcoes) -> None:
        if opcoes["substituir_revisados"] and not opcoes["forcar"]:
            raise CommandError("--substituir-revisados exige --forcar.")
        try:
            versao = VersaoDocumento.objects.select_related(
                "documento",
                "documento__tipo",
                "documento__aplicacao",
            ).get(pk=opcoes["versao"])
        except VersaoDocumento.DoesNotExist as erro:
            raise CommandError("Versão documental não encontrada.") from erro

        try:
            resultado, processamento, reutilizado = executar_segmentacao(
                versao,
                confirmar=opcoes["confirmar"],
                forcar=opcoes["forcar"],
                substituir_revisados=opcoes["substituir_revisados"],
                artefato_id=opcoes["artefato"],
            )
        except ErroSegmentacao as erro:
            raise CommandError(str(erro)) from erro

        diagnostico = resultado.como_dict()
        if opcoes["saida_json"]:
            destino = opcoes["saida_json"]
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(
                json.dumps(diagnostico, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        metricas = resultado.metricas
        modo = "reutilizado" if reutilizado else "persistido" if processamento else "simulado"
        self.stdout.write(
            self.style.SUCCESS(
                f"Segmentação {modo}: versão={versao.pk}; "
                f"artigos={metricas['artigos_detectados']}; "
                f"canônicos={metricas['artigos_canonicos']}; "
                f"anexos={metricas['anexos_detectados']}; "
                f"ocorrências={metricas['ocorrencias_detectadas']}; "
                f"cobertura={metricas['cobertura_percentual']:.2f}%."
            )
        )
        if not opcoes["confirmar"]:
            self.stdout.write(
                "Execução sem persistência. Revise o diagnóstico e repita com --confirmar."
            )
        if processamento:
            self.stdout.write(f"Processamento documental: {processamento.pk}.")
