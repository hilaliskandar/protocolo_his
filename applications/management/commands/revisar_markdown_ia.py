from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from applications.models import VersaoDocumento
from applications.revisao_ia import ErroRevisaoIALocal, executar_revisao_versao


class Command(BaseCommand):
    help = "Revisa o Markdown convertido com IA local sem sobrescrever a conversão original."

    def add_arguments(self, parser) -> None:
        grupo = parser.add_mutually_exclusive_group(required=True)
        grupo.add_argument("--aplicacao", type=int)
        grupo.add_argument("--documento", type=int)
        grupo.add_argument("--versao", type=int)
        parser.add_argument("--modelo", required=True)
        parser.add_argument("--forcar", action="store_true")
        parser.add_argument("--falhar-rapido", action="store_true")
        parser.add_argument("--max-caracteres", type=int, default=8_000)
        parser.add_argument("--confianca-minima", type=float, default=0.9)
        parser.add_argument("--alteracao-maxima", type=float, default=0.2)
        parser.add_argument("--remocao-maxima", type=float, default=0.08)

    def handle(self, *args, **opcoes) -> None:
        if opcoes["max_caracteres"] < 1_000:
            raise CommandError("--max-caracteres deve ser pelo menos 1000.")
        for nome in ("confianca_minima", "alteracao_maxima", "remocao_maxima"):
            if not 0 <= opcoes[nome] <= 1:
                raise CommandError(f"--{nome.replace('_', '-')} deve estar entre 0 e 1.")

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
        for versao in versoes:
            try:
                processamento = executar_revisao_versao(
                    versao,
                    modelo=opcoes["modelo"],
                    forcar=opcoes["forcar"],
                    max_caracteres=opcoes["max_caracteres"],
                    confianca_minima=opcoes["confianca_minima"],
                    alteracao_maxima=opcoes["alteracao_maxima"],
                    remocao_maxima=opcoes["remocao_maxima"],
                )
            except ErroRevisaoIALocal as erro:
                falhas += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"Falha na versão {versao.pk} ({versao.nome_original}): {erro}"
                    )
                )
                if opcoes["falhar_rapido"]:
                    raise CommandError(str(erro)) from erro
                continue

            foi_reutilizado = not opcoes["forcar"] and processamento.criado_em < processamento.atualizado_em
            if foi_reutilizado:
                reutilizados += 1
                acao = "reutilizada"
            else:
                sucessos += 1
                acao = "concluída"
            self.stdout.write(
                self.style.SUCCESS(
                    f"Versão {versao.pk}: revisão {acao}; "
                    f"unidades={processamento.metricas.get('unidades_total', 0)}; "
                    f"autoaprovadas={processamento.metricas.get('unidades_autoaprovadas', 0)}; "
                    f"bloqueadas={processamento.metricas.get('unidades_bloqueadas', 0)}."
                )
            )

        resumo = (
            f"Revisão encerrada: {sucessos} concluída(s), "
            f"{reutilizados} reutilizada(s), {falhas} falha(s)."
        )
        if falhas:
            self.stderr.write(self.style.WARNING(resumo))
            raise CommandError(resumo)
        self.stdout.write(self.style.SUCCESS(resumo))
