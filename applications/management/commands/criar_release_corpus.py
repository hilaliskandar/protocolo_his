from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from applications.models import (
    AplicacaoMunicipal,
    DocumentoNormativo,
    OcorrenciaDocumental,
    ReleaseCorpus,
    ReleaseCorpusDocumento,
    VersaoDocumento,
)


class Command(BaseCommand):
    help = "Cria uma release de corpus com as versões documentais liberadas da aplicação."

    def add_arguments(self, parser) -> None:
        parser.add_argument("aplicacao_pk", type=int)
        parser.add_argument("--versao", required=True)
        parser.add_argument("--liberado", action="store_true")

    def handle(self, *args, **opcoes) -> None:
        try:
            aplicacao = AplicacaoMunicipal.objects.select_related("municipio").get(
                pk=opcoes["aplicacao_pk"]
            )
        except AplicacaoMunicipal.DoesNotExist as erro:
            raise CommandError("A aplicação municipal informada não existe.") from erro

        if ReleaseCorpus.objects.filter(
            aplicacao=aplicacao,
            versao=opcoes["versao"],
        ).exists():
            raise CommandError("Já existe uma release de corpus com esta versão para a aplicação.")

        versoes_liberadas = list(
            VersaoDocumento.objects.select_related("documento", "documento__tipo")
            .filter(
                documento__aplicacao=aplicacao,
                documento__status=DocumentoNormativo.Status.LIBERADO,
            )
            .order_by("documento__ano", "documento__numero", "versao", "pk")
        )
        if not versoes_liberadas:
            raise CommandError("A aplicação não possui versões documentais liberadas.")

        bloqueios = list(
            OcorrenciaDocumental.objects.select_related("versao_documento", "ato", "artigo", "anexo")
            .filter(
                versao_documento__in=versoes_liberadas,
                severidade=OcorrenciaDocumental.Severidade.CRITICA,
            )
            .exclude(
                estado__in=[
                    OcorrenciaDocumental.Estado.RESOLVIDA,
                    OcorrenciaDocumental.Estado.ACEITA,
                ]
            )
            .order_by("versao_documento_id", "pagina", "pk")
        )
        if bloqueios:
            self.stderr.write(
                self.style.ERROR(
                    f"Foram encontradas {len(bloqueios)} ocorrência(s) crítica(s) bloqueando a release:"
                )
            )
            for ocorrencia in bloqueios:
                pagina = f" página {ocorrencia.pagina}" if ocorrencia.pagina else ""
                self.stderr.write(
                    self.style.ERROR(
                        f"- ocorrência {ocorrencia.pk} na versão {ocorrencia.versao_documento_id}{pagina}: "
                        f"{ocorrencia.categoria} ({ocorrencia.get_estado_display()})"
                    )
                )
            raise CommandError("A release não pode ser criada enquanto existirem ocorrências críticas abertas.")

        estado = ReleaseCorpus.Estado.LIBERADO if opcoes["liberado"] else ReleaseCorpus.Estado.RASCUNHO
        with transaction.atomic():
            release = ReleaseCorpus.objects.create(
                aplicacao=aplicacao,
                versao=opcoes["versao"],
                estado=estado,
                metricas={"total_versoes_documentais": len(versoes_liberadas)},
                liberado_em=timezone.now() if opcoes["liberado"] else None,
            )
            ReleaseCorpusDocumento.objects.bulk_create(
                [
                    ReleaseCorpusDocumento(
                        release=release,
                        versao_documento=versao_documento,
                    )
                    for versao_documento in versoes_liberadas
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Release criada com sucesso: pk={release.pk}, versão={release.versao}, "
                f"estado={release.get_estado_display()}, documentos={len(versoes_liberadas)}."
            )
        )
