from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from applications.models import VersaoDocumento
from applications.qualificacao import ErroQualificacaoDocumento, qualificar_versao


class Command(BaseCommand):
    help = "Qualifica versões documentais usando o motor do conversor-his."

    def add_arguments(self, parser) -> None:
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument("--aplicacao", type=int)
        grupo.add_argument("--documento", type=int)
        grupo.add_argument("--versao", type=int)
        parser.add_argument("--forcar", action="store_true")
        parser.add_argument("--falhar-rapido", action="store_true")
        parser.add_argument("--min-caracteres-nativos", type=int, default=40)

    def handle(self, *args, **opcoes) -> None:
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

        sucessos = 0
        reutilizados = 0
        falhas = 0
        parametros = {"min_native_chars": opcoes["min_caracteres_nativos"]}

        for versao in versoes:
            processamento_anterior = versao.processamentos.filter(
                etapa="qualificacao",
                status="concluido",
                parametros=parametros,
            ).first()
            try:
                processamento = qualificar_versao(
                    versao,
                    forcar=opcoes["forcar"],
                    parametros=parametros,
                )
            except ErroQualificacaoDocumento as erro:
                falhas += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"Falha na versão {versao.pk} ({versao.nome_original}): {erro}"
                    )
                )
                if opcoes["falhar_rapido"]:
                    raise CommandError(str(erro)) from erro
                continue

            if processamento_anterior and processamento.pk == processamento_anterior.pk:
                reutilizados += 1
                acao = "reutilizado"
            else:
                sucessos += 1
                acao = "concluído"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Versão {versao.pk}: diagnóstico {acao}; "
                    f"rota={processamento.rota_documento}; "
                    f"páginas={processamento.metricas.get('paginas_total', 0)}."
                )
            )

        resumo = (
            f"Qualificação encerrada: {sucessos} concluída(s), "
            f"{reutilizados} reutilizada(s), {falhas} falha(s)."
        )
        if falhas:
            self.stderr.write(self.style.WARNING(resumo))
            raise CommandError(resumo)
        self.stdout.write(self.style.SUCCESS(resumo))
