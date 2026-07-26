from django.apps import AppConfig


class ApplicationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "applications"
    verbose_name = "Aplicações do Protocolo HIS"

    def ready(self) -> None:
        from .compatibilidade_arquivos import aplicar_correcao_fieldfile

        aplicar_correcao_fieldfile()
