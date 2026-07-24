import json
from datetime import date
from hashlib import sha256
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from applications.models import Municipio

URL_IBGE_BRASIL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome"
URL_IBGE_UF = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios?orderBy=nome"
)


class Command(BaseCommand):
    help = "Carrega ou atualiza a referência oficial de municípios do IBGE."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--arquivo", type=Path)
        parser.add_argument("--uf", type=str)
        parser.add_argument("--data-referencia", type=date.fromisoformat)

    def handle(self, *args, **opcoes) -> None:
        filtro_uf = opcoes["uf"].upper() if opcoes["uf"] else None
        dados_brutos, fonte = self._obter_dados(opcoes["arquivo"], filtro_uf)
        resumo_fonte = sha256(dados_brutos).hexdigest()
        data_referencia = opcoes["data_referencia"] or timezone.localdate()
        registros = self._carregar_json(dados_brutos)

        if not isinstance(registros, list):
            raise CommandError("A fonte do IBGE deve conter uma lista de municípios.")

        caminho_fotografia = self._preservar_fotografia(dados_brutos, resumo_fonte, data_referencia)
        criados = 0
        atualizados = 0
        codigos_processados: set[str] = set()

        with transaction.atomic():
            for registro in registros:
                municipio = self._normalizar_registro(registro)
                if filtro_uf and municipio["uf"] != filtro_uf:
                    continue
                codigos_processados.add(municipio["codigo_ibge"])
                _, criado = Municipio.objects.update_or_create(
                    codigo_ibge=municipio["codigo_ibge"],
                    defaults={
                        **municipio,
                        "ativo": True,
                        "fonte_dados": fonte,
                        "data_referencia": data_referencia,
                        "sha256_fonte": resumo_fonte,
                    },
                )
                criados += int(criado)
                atualizados += int(not criado)

            if not codigos_processados:
                raise CommandError("Nenhum município foi encontrado para o filtro informado.")

            consulta_inativacao = Municipio.objects.exclude(codigo_ibge__in=codigos_processados)
            if filtro_uf:
                consulta_inativacao = consulta_inativacao.filter(uf=filtro_uf)
            inativados = consulta_inativacao.update(ativo=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga concluída: {criados} criados, {atualizados} atualizados, "
                f"{inativados} inativados. Fotografia: {caminho_fotografia}"
            )
        )

    def _obter_dados(self, caminho: Path | None, uf: str | None) -> tuple[bytes, str]:
        if caminho:
            try:
                return caminho.read_bytes(), caminho.resolve().as_uri()
            except OSError as erro:
                raise CommandError(f"Não foi possível ler o arquivo: {caminho}") from erro

        url = URL_IBGE_UF.format(uf=uf) if uf else URL_IBGE_BRASIL
        requisicao = Request(
            url,
            headers={
                "Accept": "application/json, text/plain",
                "Accept-Encoding": "identity",
                "User-Agent": "Protocolo-HIS/1.0",
            },
        )
        try:
            with urlopen(requisicao, timeout=60) as resposta:
                return resposta.read(), url
        except (OSError, URLError) as erro:
            raise CommandError("Não foi possível consultar a API oficial do IBGE.") from erro

    @staticmethod
    def _carregar_json(dados: bytes) -> object:
        try:
            texto = dados.decode("utf-8-sig")
        except UnicodeDecodeError as erro:
            raise CommandError("A fonte de municípios não está codificada em UTF-8.") from erro

        try:
            return json.loads(texto)
        except json.JSONDecodeError as erro:
            amostra = " ".join(texto[:160].split())
            raise CommandError(
                "A fonte de municípios não contém JSON válido. "
                f"Conteúdo inicial recebido: {amostra!r}"
            ) from erro

    def _preservar_fotografia(self, dados: bytes, resumo: str, referencia: date) -> Path:
        diretorio = Path(settings.PROTOCOL_DATA_ROOT) / "referencias" / "ibge"
        diretorio.mkdir(parents=True, exist_ok=True)
        caminho = diretorio / f"municipios_{referencia.isoformat()}_{resumo[:12]}.json"
        if not caminho.exists():
            caminho.write_bytes(dados)
        return caminho

    @staticmethod
    def _normalizar_registro(registro: dict) -> dict[str, str]:
        try:
            unidade_federacao = registro["microrregiao"]["mesorregiao"]["UF"]
            codigo_ibge = str(registro["id"])
            nome = str(registro["nome"]).strip()
            codigo_uf = str(unidade_federacao["id"])
            uf = str(unidade_federacao["sigla"]).strip().upper()
            nome_uf = str(unidade_federacao["nome"]).strip()
        except (KeyError, TypeError, ValueError) as erro:
            raise CommandError("A estrutura da resposta do IBGE é incompatível.") from erro

        if len(codigo_ibge) != 7 or len(uf) != 2 or not nome:
            raise CommandError("A fonte contém um município com identificação inválida.")
        return {
            "codigo_ibge": codigo_ibge,
            "nome": nome,
            "codigo_uf": codigo_uf,
            "uf": uf,
            "nome_uf": nome_uf,
        }
