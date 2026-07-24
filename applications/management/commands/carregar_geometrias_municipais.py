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

URL_BASE_GEODATA = (
    "https://git.c3sl.ufpr.br/simcaq/geodata-br/-/raw/master/geojson/"
    "geojs-{codigo_uf}-mun.json"
)
PROPRIEDADES_CODIGO = ("id", "code_muni", "codarea", "CD_MUN", "codigo_ibge")
TIPOS_GEOMETRIA_ACEITOS = {"Polygon", "MultiPolygon"}


class Command(BaseCommand):
    help = "Carrega geometrias municipais GeoJSON e as vincula pelo código IBGE."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--arquivo", type=Path)
        parser.add_argument("--uf", type=str)
        parser.add_argument("--codigo-uf", type=str)
        parser.add_argument("--data-referencia", type=date.fromisoformat)
        parser.add_argument("--ignorar-ausentes", action="store_true")

    def handle(self, *args, **opcoes) -> None:
        filtro_uf = opcoes["uf"].upper() if opcoes["uf"] else None
        codigo_uf = self._resolver_codigo_uf(filtro_uf, opcoes["codigo_uf"])
        dados_brutos, fonte = self._obter_dados(opcoes["arquivo"], codigo_uf)
        resumo_fonte = sha256(dados_brutos).hexdigest()
        data_referencia = opcoes["data_referencia"] or timezone.localdate()
        colecao = self._carregar_json(dados_brutos)

        feicoes = self._validar_colecao(colecao)
        caminho_fotografia = self._preservar_fotografia(
            dados_brutos,
            resumo_fonte,
            data_referencia,
            codigo_uf,
        )

        atualizados = 0
        ausentes: list[str] = []
        codigos_processados: set[str] = set()
        instante = timezone.now()

        with transaction.atomic():
            for feicao in feicoes:
                codigo_ibge = self._obter_codigo_ibge(feicao)
                if codigo_ibge in codigos_processados:
                    raise CommandError(f"Código IBGE repetido no GeoJSON: {codigo_ibge}")
                codigos_processados.add(codigo_ibge)

                try:
                    municipio = Municipio.objects.get(codigo_ibge=codigo_ibge)
                except Municipio.DoesNotExist:
                    ausentes.append(codigo_ibge)
                    continue

                if filtro_uf and municipio.uf != filtro_uf:
                    raise CommandError(
                        f"A feição {codigo_ibge} pertence a {municipio.uf}, não a {filtro_uf}."
                    )

                municipio.geometria_geojson = feicao["geometry"]
                municipio.fonte_geometria = fonte
                municipio.data_referencia_geometria = data_referencia
                municipio.sha256_geometria = resumo_fonte
                municipio.geometria_atualizada_em = instante
                municipio.save(
                    update_fields=[
                        "geometria_geojson",
                        "fonte_geometria",
                        "data_referencia_geometria",
                        "sha256_geometria",
                        "geometria_atualizada_em",
                        "atualizado_em",
                    ]
                )
                atualizados += 1

            if ausentes and not opcoes["ignorar_ausentes"]:
                amostra = ", ".join(ausentes[:10])
                sufixo = "..." if len(ausentes) > 10 else ""
                raise CommandError(
                    "Há códigos no GeoJSON sem município previamente carregado no IBGE: "
                    f"{amostra}{sufixo}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga concluída: {atualizados} geometrias atualizadas, "
                f"{len(ausentes)} códigos ausentes. Fotografia: {caminho_fotografia}"
            )
        )

    @staticmethod
    def _resolver_codigo_uf(uf: str | None, codigo_informado: str | None) -> str:
        if codigo_informado:
            codigo = codigo_informado.strip()
            if len(codigo) != 2 or not codigo.isdigit():
                raise CommandError("O código da UF deve conter dois dígitos.")
            return codigo
        if not uf:
            raise CommandError("Informe --uf ou --codigo-uf quando não usar --arquivo.")
        codigos = set(
            Municipio.objects.filter(uf=uf, codigo_uf__gt="").values_list("codigo_uf", flat=True)
        )
        if len(codigos) != 1:
            raise CommandError(
                f"Não foi possível determinar um único código IBGE para a UF {uf}."
            )
        return codigos.pop()

    def _obter_dados(self, caminho: Path | None, codigo_uf: str) -> tuple[bytes, str]:
        if caminho:
            try:
                return caminho.read_bytes(), caminho.resolve().as_uri()
            except OSError as erro:
                raise CommandError(f"Não foi possível ler o arquivo: {caminho}") from erro

        url = URL_BASE_GEODATA.format(codigo_uf=codigo_uf)
        requisicao = Request(
            url,
            headers={
                "Accept": "application/geo+json, application/json, text/plain",
                "Accept-Encoding": "identity",
                "User-Agent": "Protocolo-HIS/1.0",
            },
        )
        try:
            with urlopen(requisicao, timeout=120) as resposta:
                return resposta.read(), url
        except (OSError, URLError) as erro:
            raise CommandError("Não foi possível consultar a fonte GeoJSON.") from erro

    @staticmethod
    def _carregar_json(dados: bytes) -> object:
        try:
            texto = dados.decode("utf-8-sig")
        except UnicodeDecodeError as erro:
            raise CommandError("A fonte de geometrias não está codificada em UTF-8.") from erro

        try:
            return json.loads(texto)
        except json.JSONDecodeError as erro:
            amostra = " ".join(texto[:160].split())
            raise CommandError(
                "A fonte de geometrias não contém JSON válido. "
                f"Conteúdo inicial recebido: {amostra!r}"
            ) from erro

    def _preservar_fotografia(
        self,
        dados: bytes,
        resumo: str,
        referencia: date,
        codigo_uf: str,
    ) -> Path:
        diretorio = Path(settings.PROTOCOL_DATA_ROOT) / "referencias" / "geometrias"
        diretorio.mkdir(parents=True, exist_ok=True)
        caminho = diretorio / (
            f"municipios_uf_{codigo_uf}_{referencia.isoformat()}_{resumo[:12]}.geojson"
        )
        if not caminho.exists():
            caminho.write_bytes(dados)
        return caminho

    @staticmethod
    def _validar_colecao(colecao: object) -> list[dict]:
        if not isinstance(colecao, dict) or colecao.get("type") != "FeatureCollection":
            raise CommandError("A fonte deve ser uma FeatureCollection GeoJSON.")
        feicoes = colecao.get("features")
        if not isinstance(feicoes, list) or not feicoes:
            raise CommandError("A FeatureCollection não contém feições.")

        for feicao in feicoes:
            if not isinstance(feicao, dict) or feicao.get("type") != "Feature":
                raise CommandError("A coleção contém uma feição GeoJSON inválida.")
            geometria = feicao.get("geometry")
            if not isinstance(geometria, dict):
                raise CommandError("Uma feição não contém geometria válida.")
            if geometria.get("type") not in TIPOS_GEOMETRIA_ACEITOS:
                raise CommandError("Somente geometrias Polygon e MultiPolygon são aceitas.")
            if not geometria.get("coordinates"):
                raise CommandError("Uma feição contém geometria sem coordenadas.")
        return feicoes

    @staticmethod
    def _obter_codigo_ibge(feicao: dict) -> str:
        propriedades = feicao.get("properties") or {}
        candidatos = [feicao.get("id")]
        candidatos.extend(propriedades.get(chave) for chave in PROPRIEDADES_CODIGO)

        for candidato in candidatos:
            if candidato is None:
                continue
            codigo = str(candidato).strip().removesuffix(".0")
            if codigo.isdigit() and len(codigo) == 7:
                return codigo
        raise CommandError("Uma feição não contém código IBGE municipal de sete dígitos.")
