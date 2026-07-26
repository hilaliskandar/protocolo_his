from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "applications.apps.ApplicationsConfig",
    "ingestao.apps.IngestaoConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "protocolo_his"),
        "USER": os.getenv("POSTGRES_USER", "protocolo_his"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "protocolo_his"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "55432"),
    }
}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
PROTOCOL_DATA_ROOT = Path(os.getenv("PROTOCOL_DATA_ROOT", str(BASE_DIR / "data")))
if not PROTOCOL_DATA_ROOT.is_absolute():
    PROTOCOL_DATA_ROOT = BASE_DIR / PROTOCOL_DATA_ROOT
MEDIA_ROOT = PROTOCOL_DATA_ROOT

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_REVIEW_MAX_CHARS = int(os.getenv("OLLAMA_REVIEW_MAX_CHARS", "8000"))
OLLAMA_REVIEW_MIN_CONFIDENCE = float(os.getenv("OLLAMA_REVIEW_MIN_CONFIDENCE", "0.90"))
OLLAMA_REVIEW_MAX_CHANGE = float(os.getenv("OLLAMA_REVIEW_MAX_CHANGE", "0.20"))
OLLAMA_REVIEW_MAX_REMOVAL = float(os.getenv("OLLAMA_REVIEW_MAX_REMOVAL", "0.08"))

API_INGESTAO_TOKEN = os.getenv("API_INGESTAO_TOKEN", "")
INGESTAO_MAX_ZIP_BYTES = int(os.getenv("INGESTAO_MAX_ZIP_BYTES", str(500 * 1024 * 1024)))
INGESTAO_MAX_ARQUIVOS = int(os.getenv("INGESTAO_MAX_ARQUIVOS", "1000"))
INGESTAO_MAX_DESCOMPACTADO_BYTES = int(
    os.getenv("INGESTAO_MAX_DESCOMPACTADO_BYTES", str(2 * 1024 * 1024 * 1024))
)
INGESTAO_MAX_ARQUIVO_BYTES = int(
    os.getenv("INGESTAO_MAX_ARQUIVO_BYTES", str(200 * 1024 * 1024))
)
INGESTAO_MAX_RAZAO_COMPACTACAO = float(os.getenv("INGESTAO_MAX_RAZAO_COMPACTACAO", "100"))
INGESTAO_CONFIANCA_AUTOMATICA = float(os.getenv("INGESTAO_CONFIANCA_AUTOMATICA", "0.85"))

X_FRAME_OPTIONS = "SAMEORIGIN"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
