import os

# Tests stay on in-memory channels/cache even if the shell has REDIS_URL.
os.environ.pop('REDIS_URL', None)

from .base import *

# Tests never talk to Redis even if REDIS_URL is set in the environment.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "jizz-tests",
    }
}

EBIRD_API_TOKEN = 'ebird'

ALLOWED_HOSTS = ['*']

# CSRF trusted origins for local development
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# Use POSTGRES_* env vars when set (e.g. GitHub Actions runner); otherwise local defaults
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'jizz'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.environ.get('POSTGRES_HOST', '127.0.0.1'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

# Email settings for MailCatcher (local development)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'localhost'
EMAIL_PORT = 1025
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = 'info@birdr.pro'


SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = "key"
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = "secret"
SOCIAL_AUTH_APPLE_ID_SECRET = 'your-actual-apple-secret'

OPENAI_API_KEY = 'key'


CORNELL_USERNAME = 'username'
CORNELL_PASSWORD = 'password'

XENO_CANTO_API_KEY = 'key'
