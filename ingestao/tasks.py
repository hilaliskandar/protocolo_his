from prefect import flow, task

from .models import ImportacaoLote
from .services import confirmar_lote, inspecionar_lote


@task(retries=1, retry_delay_seconds=10)
def tarefa_inspecionar_lote(lote_id: str) -> dict:
    lote = ImportacaoLote.objects.get(pk=lote_id)
    inspecionar_lote(lote)
    return lote.metricas


@task(retries=1, retry_delay_seconds=10)
def tarefa_confirmar_lote(lote_id: str) -> dict:
    lote = ImportacaoLote.objects.get(pk=lote_id)
    return confirmar_lote(lote)


@flow(name="inspecionar-lote-documental")
def fluxo_inspecionar_lote(lote_id: str) -> dict:
    return tarefa_inspecionar_lote(lote_id)


@flow(name="confirmar-lote-documental")
def fluxo_confirmar_lote(lote_id: str) -> dict:
    return tarefa_confirmar_lote(lote_id)
