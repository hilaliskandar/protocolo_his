from .settings import *

# Os testes usam o mesmo backend PostgreSQL definido em config.settings.
# Somente componentes não persistentes são simplificados para acelerar a suíte.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
