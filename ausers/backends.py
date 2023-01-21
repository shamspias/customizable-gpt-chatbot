import re

from django.contrib.auth.backends import ModelBackend

from users.models import User


class EmailOrUsernameModelBackend(ModelBackend):
    def authenticate(self, request, **kwargs):
        username = kwargs['username']
        password = kwargs['password']

        if username and re.search(r'[^@\s]+@[^@\s]+\.[^@\s]+', username):
            kwargs = {'email': username}
        else:
            kwargs = {'username': username}

        try:
            user = User.objects.get(**kwargs)
        except User.DoesNotExist:
            return None
        else:
            if user.is_active and user.check_password(password):
                return user

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None