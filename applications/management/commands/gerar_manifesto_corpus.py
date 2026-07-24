from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from applications.manifesto import gerar_manifesto_csv, gerar_manifesto_json
from applications.models import AplicacaoMunicipal


class Command(BaseCommand):
    help = "Gera o manifesto do corpus de uma aplicação municipal em JSON ou CSV."

    def add_arguments(self, parser) -> None:
        parser.add_argument("aplicacao_id", type=int)
        parser.add_argument("--formato", choices=("json", "csv"), default="json")
        parser.add_argument("--saida", type=Path)

    def handle(self, *args, **opcoes) -> None:
        try:
            aplicacao = AplicacaoMunicipal.objects.select_related("municipio").get(
                pk=opcoes["aplicacao_id"]
            )
        except AplicacaoMunicipal.DoesNotExist as erro:
            raise CommandError("A aplicação municipal informada não existe.") from erro

        formato = opcoes["formato"]
        caminho_saida = opcoes["saida"]
        if caminho_saida is None:
            caminho_saida = (
                Path(settings.PROTOCOL_DATA_ROOT)
                / "manifestos"
                / f"aplicacao_{aplicacao.pk}.{formato}"
            )

        if formato == "json":
            caminho_gerado = gerar_manifesto_json(aplicacao, caminho_saida)
        else:
            caminho_gerado = gerar_manifesto_csv(aplicacao, caminho_saida)

        self.stdout.write(self.style.SUCCESS(f"Manifesto gerado em: {caminho_gerado}"))
