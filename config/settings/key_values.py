import os


# Celery
BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379')

# Google OAuth2 settings
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv('GOOGLE_KEY')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv('GOOGLE_SECRET')

# Open AI key
OPENAI_API_KEY = os.getenv('OPEN_AI_KEY')

# Pinecone
PINECONE_KEY = os.getenv('PINECONE_KEY')
PINECONE_ENVIRONMENT = os.getenv('PINECONE_ENVIRONMENT')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME')

# Admin Site Config
ADMIN_SITE_HEADER = os.getenv('ADMIN_SITE_HEADER')
ADMIN_SITE_TITLE = os.getenv('ADMIN_SITE_TITLE')
ADMIN_SITE_INDEX = os.getenv('ADMIN_SITE_INDEX')

# OAuth2 settings
APPLICATION_NAME = os.getenv('APPLICATION_NAME', 'chatbot')
