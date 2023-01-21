import sentry_sdk
import os
import sys

from datetime import timedelta
from pathlib import Path
from corsheaders.defaults import default_headers
from dotenv import load_dotenv
from sentry_sdk.integrations.django import DjangoIntegration

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv()

TESTING = sys.argv[1:2] == ['test']

SITE_URL = os.getenv('SITE_URL', 'http://localhost:8000')

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'django_filters',
    'drf_yasg',  # another way to swagger
    'rest_framework_simplejwt.token_blacklist',
    'channels',
    'corsheaders',  # Cross Origin
    'easy_thumbnails',  # image lib
    'social_django',  # django social auth
    'rest_social_auth',  # this package
]

LOCAL_APPS = [
    'ausers.apps.AusersConfig',
    'common.apps.CommonConfig',
    'notifications.apps.NotificationsConfig',

]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

DEBUG = os.getenv('DJANGO_DEBUG', False) == 'True'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # CROSS Origin
    'corsheaders.middleware.CorsMiddleware',
]

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-z#p-sa90q*k(n9xh132k@rgo=sd3@501=(%l8xpn=c-+yr&q=0')
ROOT_URLCONF = 'customizableGpt3Chatbot.urls'
WSGI_APPLICATION = 'customizableGpt3Chatbot.wsgi.application'
ASGI_APPLICATION = 'customizableGpt3Chatbot.asgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

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

# Email
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = os.getenv('EMAIL_PORT', 1025)
EMAIL_FROM = os.getenv('EMAIL_FROM', 'noreply@somehost.local')

EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'shamspias0!@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', 'password')

# Celery
BROKER_URL = os.getenv('BROKER_URL', 'redis://redis:6379')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379')

ADMINS = ()

# Sentry
sentry_sdk.init(dsn=os.getenv('SENTRY_DSN', ''), integrations=[DjangoIntegration()])

# CORS

CSRF_COOKIE_SECURE = bool(os.getenv('CSRF_COOKIE_SECURE', True))
SESSION_COOKIE_SECURE = bool(os.getenv('SESSION_COOKIE_SECURE', True))

# False since we will grab it via universal-cookies
CSRF_COOKIE_HTTPONLY = bool(os.getenv('CSRF_COOKIE_HTTPONLY', False))

SESSION_COOKIE_HTTPONLY = bool(os.getenv('SESSION_COOKIE_HTTPONLY', True))
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', "None")
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', "None")
CORS_ALLOW_CREDENTIALS = bool(os.getenv('CORS_ALLOW_CREDENTIALS', True))
CORS_ORIGIN_ALLOW_ALL = bool(os.getenv('CORS_ORIGIN_ALLOW_ALL', False))
CSRF_COOKIE_NAME = os.getenv('CSRF_COOKIE_NAME', "csrftoken")
#
# CORS_ALLOW_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS')
# CORS_ALLOW_ORIGINS = CORS_ALLOW_ORIGINS.split(',')
# CORS_ALLOWED_ORIGINS = CORS_ALLOW_ORIGINS
#
# CORS_ALLOW_METHODS = (
#     'GET',
#     'POST',
#     'PUT',
#     'PATCH',
#     'DELETE',
#     'OPTIONS'
# )

CORS_ALLOW_HEADERS = list(default_headers) + [
    'X-CSRFToken',
]
CORS_EXPOSE_HEADERS = ['Content-Type', 'X-CSRFToken']

# CELERY
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# GENERALS
APPEND_SLASH = bool(os.getenv('APPEND_SLASH', True))

# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = os.getenv('LANGUAGE_CODE', 'en-us')

TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')
USE_I18N = bool(os.getenv('USE_I18N', True))
USE_TZ = bool(os.getenv('USE_TZ', True))
USE_L10N = bool(os.getenv('USE_L10N', True))
LOGIN_REDIRECT_URL = '/'

# Headers
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Static files (CSS, JavaScript, Images)

STATIC_URL = 'static/'
MEDIA_URL = 'media/'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'django.server': {
            '()': 'django.utils.log.ServerFormatter',
            'format': '[%(server_time)s] %(message)s',
        },
        'verbose': {'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'},
        'simple': {'format': '%(levelname)s %(message)s'},
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'django.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'django.server',
        },
        'console': {'level': 'DEBUG', 'class': 'logging.StreamHandler', 'formatter': 'simple'},
        'mail_admins': {'level': 'ERROR', 'class': 'django.utils.log.AdminEmailHandler'},
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'propagate': True,
        },
        'django.server': {
            'handlers': ['django.server'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['mail_admins', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {'handlers': ['console'], 'level': 'INFO'},
    },
}

# Custom user app
AUTH_USER_MODEL = os.getenv('AUTH_USER_MODEL', 'ausers.User')

# Social login

REST_SOCIAL_OAUTH_REDIRECT_URI = '/'
REST_SOCIAL_DOMAIN_FROM_ORIGIN = True

# Django Rest Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend',
                                'rest_framework.filters.OrderingFilter'],
    'PAGE_SIZE': int(os.getenv('DJANGO_PAGINATION_LIMIT', 18)),
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S.%fZ',
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {'anon': '100/second', 'user': '1000/second', 'subscribe': '60/minute'},
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}

# JWT configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=3),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# summernote configuration
SUMMERNOTE_CONFIG = {
    'summernote': {
        'toolbar': [
            ['style', ['style']],
            ['font', ['bold', 'underline', 'clear']],
            ['fontname', ['fontname']],
            ['color', ['color']],
            ['para', ['ul', 'ol', 'paragraph', 'smallTagButton']],
            ['table', ['table']],
            ['insert', ['link', 'video']],
            ['view', ['fullscreen', 'codeview', 'help']],
        ]
    }
}

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
