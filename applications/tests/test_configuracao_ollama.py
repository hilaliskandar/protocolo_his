from django.conf import settings
from django.test import SimpleTestCase

from applications.management.commands.revisar_markdown_ia import Command


class TestesConfiguracaoPadraoOllama(SimpleTestCase):
    def test_comando_usa_modelo_e_gates_configurados(self):
        comando = Command()
        parser = comando.create_parser("manage.py", "revisar_markdown_ia")

        opcoes = vars(parser.parse_args(["--versao", "1"]))

        self.assertEqual(opcoes["modelo"], settings.OLLAMA_MODEL)
        self.assertEqual(opcoes["max_caracteres"], settings.OLLAMA_REVIEW_MAX_CHARS)
        self.assertEqual(opcoes["confianca_minima"], settings.OLLAMA_REVIEW_MIN_CONFIDENCE)
        self.assertEqual(opcoes["alteracao_maxima"], settings.OLLAMA_REVIEW_MAX_CHANGE)
        self.assertEqual(opcoes["remocao_maxima"], settings.OLLAMA_REVIEW_MAX_REMOVAL)
