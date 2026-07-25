from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from applications.conversao import ErroConversaoDocumento, converter_versao
from applications.models import VersaoDocumento


class Command(BaseCommand):
    help = "Converte versões documentais qualificadas usando o conversor-his."

    def add_arguments(self, parser) -> None:
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument("--aplicacao", type=int)
        grupo.add_argument("--documento", type=int)
        grupo.add_argument("--versao", type=int)
        parser.add_argument("--forcar", action="store_true")
        parser.add_argument("--falhar-rapido", action="store_true")
        parser.add_argument("--dpi", type=int, default=300)

    def handle(self, *args, **opcoes) -> None:
        if not 150 <= opcoes["dpi"] <= 600:
            raise CommandError("O DPI deve estar entre 150 e 600.")

        consulta = VersaoDocumento.objects.select_related(
            "documento",
            "documento__aplicacao",
            "documento__aplicacao__municipio",
        ).order_by("documento_id", "versao")

        if opcoes["aplicacao"] is not None:
            consulta = consulta.filter(documento__aplicacao_id=opcoes["aplicacao"])
        elif opcoes["documento"] is not None:
            consulta = consulta.filter(documento_id=opcoes["documento"])
        else:
            consulta = consulta.filter(pk=opcoes["versao"])

        versoes = list(consulta)
        if not versoes:
            raise CommandError("Nenhuma versão documental foi encontrada para o filtro informado.")

        parametros = {"dpi": opcoes["dpi"]}
        sucessos = 0
        reutilizados = 0
        falhas = 0

        for versao in versoes:
            anterior = versao.processamentos.filter(
                etapa="conversao",
                status="concluido",
                parametros=parametros,
            ).first()
            try:
                processamento = converter_versao(
                    versao,
                    forcar=opcoes["forcar"],
                    parametros=parametros,
                )
            except ErroConversaoDocumento as erro:
                falhas += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"Falha na versão {versao.pk} ({versao.nome_original}): {erro}"
                    )
                )
                if opcoes["falhar_rapido"]:
                    raise CommandError(str(erro)) from erro
                continue

            if anterior and anterior.pk == processamento.pk:
                reutilizados += 1
                acao = "reutilizada"
            else:
                sucessos += 1
                acao = "concluída"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Versão {versao.pk}: conversão {acao}; "
                    f"páginas={processamento.metricas.get('paginas_total', 0)}; "
                    f"revisão={processamento.metricas.get('total_review_pages', 0)}."
                )
            )

        resumo = (
            f"Conversão encerrada: {sucessos} concluída(s), "
            f"{reutilizados} reutilizada(s), {falhas} falha(s)."
        )
        if falhas:
            self.stderr.write(self.style.WARNING(resumo))
            raise CommandError(resumo)
        self.stdout.write(self.style.SUCCESS(resumo))
