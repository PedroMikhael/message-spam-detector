from pathlib import Path
import os
from decouple import config
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default='True', cast=bool)  # Habilitar debug via env var
ALLOWED_HOSTS = ['18.221.25.182', '127.0.0.1', 'localhost', '.ngrok-free.app', 'chatbot-spam.duckdns.org', '.hf.space', '*']
CSRF_TRUSTED_ORIGINS = ['https://*.hf.space', 'https://huggingface.co']

# Proxy reverso do HF Spaces — informa ao Django que está atrás de HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'detector',
    'drf_yasg',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'spamapi.urls'

WSGI_APPLICATION = 'spamapi.wsgi.application'

# Configuração do banco de dados
# Supabase (PostgreSQL) em produção, SQLite como fallback local
import os as _os
_data_dir = '/data' if _os.path.isdir('/data') else str(BASE_DIR)
_sqlite_fallback = f'sqlite:///{_data_dir}/db.sqlite3'
_database_url = config('DATABASE_URL', default=_sqlite_fallback)

DATABASES = {
    'default': dj_database_url.config(
        default=_database_url,
        conn_max_age=600
    )
}


STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static' 

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CORS_ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:9000",
    "https://pedromikhael-verificai.hf.space",
]
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Permite tudo em dev

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [], 
        'APP_DIRS': True,  
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',  # 
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ]
}


WHATSAPP_VERIFY_TOKEN = config('WHATSAPP_VERIFY_TOKEN', default='')

WHATSAPP_ACCESS_TOKEN = config('WHATSAPP_ACCESS_TOKEN', default='')
WHATSAPP_PHONE_NUMBER_ID = config('WHATSAPP_PHONE_NUMBER_ID', default='')

GEMINI_API_KEY = config('GEMINI_API_KEY', default='')

SAFE_BROWSING_API_KEY = config('SAFE_BROWSING_API_KEY', default='')
SAFE_BROWSING_API_KEY2 = config('SAFE_BROWSING_API_KEY2', default='')


JAZZMIN_SETTINGS = {
    "site_title": "Guardião Digital Admin",
    "site_header": "Guardião Digital",
    "site_brand": "Painel de Análise",
    "welcome_sign": "Bem-vindo ao painel do Guardião Digital",
    "copyright": "LARCES - UECE",
    "topmenu_links": [
        {"name": "Home",  "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Ver Site", "url": "/", "new_window": True},
    ],
}