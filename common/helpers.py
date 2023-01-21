from django.conf import settings


def build_absolute_uri(path):
    return f'{settings.SITE_URL}{path}'