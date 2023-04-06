from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User


class EmailBackend(BaseBackend):
    """
    Authenticate using an e-mail address.
    """

    def authenticate(self, request, email=None, password=None, **kwargs):
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
