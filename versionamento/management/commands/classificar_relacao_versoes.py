from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
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
        parser.add_argument(
            "--usuario",
            required=True,
            help="Nome de usuário responsável pela confirmação.",
        )
        parser.add_argument("--confirmar", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opcoes) -> None:
        if opcoes["origem"] is not None and not opcoes["tipo_relacao"]:
            raise CommandError("--tipo-relacao é obrigatório quando --origem é informado.")

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

        momento = timezone.now() if opcoes["confirmar"] else None
        classificacao, _ = ClassificacaoVersao.objects.get_or_create(
            versao_documento=destino
        )
        classificacao.natureza = opcoes["natureza"]
        classificacao.data_referencia_normativa = opcoes["data_referencia"]
        classificacao.referencia_atualizacao = opcoes["referencia_atualizacao"]
        classificacao.estado = (
            ClassificacaoVersao.Estado.CONFIRMADA
            if opcoes["confirmar"]
            else ClassificacaoVersao.Estado.PENDENTE
        )
        classificacao.justificativa = opcoes["justificativa"]
        classificacao.fonte = opcoes["fonte"]
        classificacao.confirmado_por = usuario if opcoes["confirmar"] else None
        classificacao.confirmado_em = momento
        classificacao.full_clean()
        classificacao.save()

        relacao = None
        if opcoes["origem"] is not None:
            try:
                origem = VersaoDocumento.objects.select_related("documento__aplicacao").get(
                    pk=opcoes["origem"]
                )
            except VersaoDocumento.DoesNotExist as erro:
                raise CommandError("Versão de origem não encontrada.") from erro

            relacao, _ = RelacaoVersoes.objects.get_or_create(
                versao_origem=origem,
                versao_destino=destino,
                tipo=opcoes["tipo_relacao"],
                defaults={"justificativa": opcoes["justificativa"]},
            )
            relacao.estado = (
                RelacaoVersoes.Estado.CONFIRMADA
                if opcoes["confirmar"]
                else RelacaoVersoes.Estado.PENDENTE
            )
            relacao.justificativa = opcoes["justificativa"]
            relacao.fonte = opcoes["fonte"]
            relacao.validado_por = usuario if opcoes["confirmar"] else None
            relacao.validado_em = momento
            relacao.full_clean()
            relacao.save()

        mensagem = f"Classificação {classificacao.pk} registrada para a versão {destino.pk}."
        if relacao:
            mensagem += f" Relação {relacao.pk} registrada."
        self.stdout.write(self.style.SUCCESS(mensagem))
