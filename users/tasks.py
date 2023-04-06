from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_forgot_password_email(subject, message, recipient):
    """
    Send an email for a forgotten password.
    """
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [recipient],
        fail_silently=False,
    )
