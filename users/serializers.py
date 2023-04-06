from rest_framework import serializers
from django.contrib.auth import get_user_model
from oauth2_provider.models import get_application_model
from oauthlib.common import generate_token
from oauth2_provider.settings import oauth2_settings
from oauth2_provider.models import AccessToken, RefreshToken
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

Application = get_application_model()
User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    User registration serializer.
    """
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name']

    def create(self, validated_data):
        username = validated_data['username']
        email = validated_data['email']
        password = validated_data.pop('password')
        first_name = validated_data['first_name']
        last_name = validated_data['last_name']

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Generate tokens for the user
        app = Application.objects.get(name=settings.APPLICATION_NAME)
        access_token = generate_token()
        refresh_token = generate_token()

        AccessToken.objects.create(
            user=user,
            token=access_token,
            application=app,
            scope=oauth2_settings.DEFAULT_SCOPES,
            expires=timezone.now() + timedelta(seconds=oauth2_settings.ACCESS_TOKEN_EXPIRE_SECONDS)
        )

        RefreshToken.objects.create(
            user=user,
            token=refresh_token,
            application=app,
            access_token=AccessToken.objects.get(token=access_token)
        )

        tokens = {
            'access_token': access_token,
            'refresh_token': refresh_token
        }

        return tokens


class UserProfileSerializer(serializers.ModelSerializer):
    """
    User profile serializer.
    """

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone_number', 'address', 'profile_picture']
        read_only_fields = ['username', 'email']
