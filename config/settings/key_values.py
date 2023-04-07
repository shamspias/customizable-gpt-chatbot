import os
from corsheaders.defaults import default_headers
from urllib.parse import quote

# Celery
BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379')

# Google OAuth2 settings
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv('GOOGLE_KEY')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv('GOOGLE_SECRET')

# Open AI key
OPENAI_API_KEY = os.getenv('OPEN_AI_KEY')

# Pinecone key
# PINECONE_KEY = os.getenv('PINECONE_KEY')


# Admin Site Config
ADMIN_SITE_HEADER = os.getenv('ADMIN_SITE_HEADER')
ADMIN_SITE_TITLE = os.getenv('ADMIN_SITE_TITLE')
ADMIN_SITE_INDEX = os.getenv('ADMIN_SITE_INDEX')

# OAuth2 settings
APPLICATION_NAME = os.getenv('APPLICATION_NAME', 'chatbot')

# CORS

CSRF_COOKIE_SECURE = bool(os.getenv('CSRF_COOKIE_SECURE', True))
SESSION_COOKIE_SECURE = bool(os.getenv('SESSION_COOKIE_SECURE', True))

# False since we will grab it via universal-cookies
CSRF_COOKIE_HTTPONLY = bool(os.getenv('CSRF_COOKIE_HTTPONLY', False))

SESSION_COOKIE_HTTPONLY = bool(os.getenv('SESSION_COOKIE_HTTPONLY', True))
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', "None")
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', "None")
CORS_ALLOW_CREDENTIALS = bool(os.getenv('CORS_ALLOW_CREDENTIALS', True))
CORS_ORIGIN_ALLOW_ALL = bool(os.getenv('CORS_ORIGIN_ALLOW_ALL', True))
CSRF_COOKIE_NAME = os.getenv('CSRF_COOKIE_NAME', "csrftoken")
#
# CORS_ALLOW_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS')
# CORS_ALLOW_ORIGINS = CORS_ALLOW_ORIGINS.split(',')
# CORS_ALLOWED_ORIGINS = CORS_ALLOW_ORIGINS
#
CORS_ALLOW_METHODS = (
    'GET',
    'POST',
    'PUT',
    'PATCH',
    'DELETE',
    'OPTIONS'
)

CORS_ALLOW_HEADERS = list(default_headers) + [
    'X-CSRFToken',
]
CORS_EXPOSE_HEADERS = ['Content-Type', 'X-CSRFToken']

X_FRAME_OPTIONS = os.getenv('X_FRAME_OPTIONS', 'DENY')
SECURE_BROWSER_XSS_FILTER = bool(os.getenv('SECURE_BROWSER_XSS_FILTER', True))
# GENERALS
APPEND_SLASH = bool(os.getenv('APPEND_SLASH', True))

LANGUAGE_CODE = os.getenv('LANGUAGE_CODE', 'en-us')

TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')
USE_I18N = bool(os.getenv('USE_I18N', True))
USE_TZ = bool(os.getenv('USE_TZ', True))
USE_L10N = bool(os.getenv('USE_L10N', True))
