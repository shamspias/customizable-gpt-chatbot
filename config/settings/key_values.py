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
