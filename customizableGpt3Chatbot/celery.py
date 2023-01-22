from __future__ import absolute_import

import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "customizableGpt3Chatbot.settings")

app = Celery('customizableGpt3Chatbot')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
# app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
