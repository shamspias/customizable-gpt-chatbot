from django.apps import AppConfig


class AusersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ausers'

    def ready(self):
        import ausers.signals
