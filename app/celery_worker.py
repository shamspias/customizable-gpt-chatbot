from celery import Celery
from app.config import settings


def create_celery_app():
    celery_app = Celery('legaldata_celery', broker=settings.CELERY_BROKER_URL)
    celery_app.conf.update(task_serializer='json',
                           accept_content=['json'],
                           result_serializer='json',
                           timezone='UTC',
                           enable_utc=True)
    return celery_app


celery_app = create_celery_app()
