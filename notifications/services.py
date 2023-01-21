import logging
from actstream import action

from notifications.channels.email import EmailChannel

logger = logging.getLogger(__name__)

ACTIVITY_USER_RESETS_PASS = 'started password reset process'

NOTIFICATIONS = {
    ACTIVITY_USER_RESETS_PASS: {
        'email': {
            'email_subject': 'Password Reset',
            'email_html_template': 'emails/user_reset_password.html',
        }
    }
}


def _send_email(email_notification_config, context, to):
    email_html_template = email_notification_config.get('email_html_template')
    email_subject = email_notification_config.get('email_subject')

    EmailChannel.send(context=context, html_template=email_html_template, subject=email_subject, to=to)


def notify(verb, **kwargs):
    notification_config = NOTIFICATIONS.get(verb)

    if notification_config and notification_config.get('email'):
        email_notification_config = notification_config.get('email')
        context = kwargs.get('context', {})
        email_to = kwargs.get('email_to', [])

        if not email_to:
            logger.debug('Please provide list of emails (email_to argument).')

        _send_email(email_notification_config, context, email_to)


# Use only with actstream activated
def send_action(sender, verb, action_object, target, **kwargs):
    action.send(sender=sender, verb=verb, action_object=action_object, target=target)
    notify(verb, **kwargs)
