from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from applications.models import VersaoDocumento
from versionamento.models import ClassificacaoVersao, RelacaoVersoes


class Command(BaseCommand):
    help = "Registra classificação de versão e, opcionalmente, relação auditável entre versões."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--destino", type=int, required=True, help="ID da versão a classificar.")
        parser.add_argument("--origem", type=int, help="ID da versão anterior relacionada.")
        parser.add_argument("--natureza", choices=ClassificacaoVersao.Natureza.values, required=True)
        parser.add_argument("--tipo-relacao", choices=RelacaoVersoes.Tipo.values)
        parser.add_argument("--data-referencia", type=date.fromisoformat)
        parser.add_argument("--referencia-atualizacao", default="")
        parser.add_argument("--justificativa", required=True)
        parser.add_argument("--fonte", default="")
        parser.add_argument("--usuario", required=True, help="Nome de usuário responsável pela confirmação.")
        parser.add_argument("--confirmar", action="store_true")

    def handle(self, *args, **opcoes) -> None:
        try:
            destino = VersaoDocumento.objects.select_related("documento__aplicacao").get(
                pk=opcoes["destino"]
            )
        except VersaoDocumento.DoesNotExist as erro:
            raise CommandError("Versão de destino não encontrada.") from erro

        usuario_model = get_user_model()
        try:
            usuario = usuario_model.objects.get(username=opcoes["usuario"])
        except usuario_model.DoesNotExist as erro:
            raise CommandError("Usuário responsável não encontrado.") from erro

        estado_classificacao = (
            ClassificacaoVersao.Estado.CONFIRMADA
            if opcoes["confirmar"]
            else ClassificacaoVersao.Estado.PENDENTE
        )
        momento = timezone.now() if opcoes["confirmar"] else None
        classificacao, _ = ClassificacaoVersao.objects.update_or_create(
            versao_documento=destino,
            defaults={
                "natureza": opcoes["natureza"],
                "data_referencia_normativa": opcoes["data_referencia"],
                "referencia_atualizacao": opcoes["referencia_atualizacao"],
                "estado": estado_classificacao,
                "justificativa": opcoes["justificativa"],
                "fonte": opcoes["fonte"],
                "confirmado_por": usuario if opcoes["confirmar"] else None,
                "confirmado_em": momento,
            },
        )
        classificacao.full_clean()
        classificacao.save()

        relacao = None
        if opcoes["origem"] is not None:
            if not opcoes["tipo_relacao"]:
                raise CommandError("--tipo-relacao é obrigatório quando --origem é informado.")
            try:
                origem = VersaoDocumento.objects.select_related("documento__aplicacao").get(
                    pk=opcoes["origem"]
                )
            except VersaoDocumento.DoesNotExist as erro:
                raise CommandError("Versão de origem não encontrada.") from erro

            estado_relacao = (
                RelacaoVersoes.Estado.CONFIRMADA
                if opcoes["confirmar"]
                else RelacaoVersoes.Estado.PENDENTE
            )
            relacao, _ = RelacaoVersoes.objects.update_or_create(
                versao_origem=origem,
                versao_destino=destino,
                tipo=opcoes["tipo_relacao"],
                defaults={
                    "estado": estado_relacao,
                    "justificativa": opcoes["justificativa"],
                    "fonte": opcoes["fonte"],
                    "validado_por": usuario if opcoes["confirmar"] else None,
                    "validado_em": momento,
                },
            )
            relacao.full_clean()
            relacao.save()

        mensagem = f"Classificação {classificacao.pk} registrada para a versão {destino.pk}."
        if relacao:
            mensagem += f" Relação {relacao.pk} registrada."
        self.stdout.write(self.style.SUCCESS(mensagem))
