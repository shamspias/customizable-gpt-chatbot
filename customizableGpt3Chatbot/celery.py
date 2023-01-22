# Start Celery with Redis

# from __future__ import absolute_import
#
# import os
#
# from celery import Celery
# from django.conf import settings
#
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "customizableGpt3Chatbot.settings")
#
# app = Celery('customizableGpt3Chatbot')
#
# app.config_from_object('django.conf:settings', namespace='CELERY')
# app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# tasks can be added below

# End Celery with Redis

# start Celery with SQS

from django.conf import settings
from boto3.session import Session
from celery import Celery

app = Celery('customizableGpt3Chatbot')

# Use SQS as the message broker
session = Session(
    aws_access_key_id=settings.AWS_ACCESS_KEY,
    aws_secret_access_key=settings.AWS_SECRET_KEY,
    region_name=settings.REGION_NAME
)
sqs = session.resource('sqs', region_name=settings.REGION_NAME)
queue = sqs.get_queue_by_name(QueueName=settings.QUEUE_NAME)
app.conf.broker_url = queue.url
app.conf.result_backend = None

# End Celery with SQS
