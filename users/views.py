from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .serializers import UserRegistrationSerializer, UserProfileSerializer
from .tasks import send_forgot_password_email
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from social_django.utils import load_strategy
from rest_framework import permissions
from rest_framework import status
from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework.response import Response
from rest_framework.views import APIView
from oauth2_provider.models import Application
from oauthlib.common import generate_token
from oauth2_provider.settings import oauth2_settings
from oauth2_provider.models import AccessToken, RefreshToken
from django.conf import settings

User = get_user_model()


class LoginView(APIView):
    """
    Login API view.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")
        client_id = request.data.get("client_id")
        client_secret = request.data.get("client_secret")

        if username is None or password is None or client_id is None or client_secret is None:
            return Response({"error": "username, password, client_id, and client_secret are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if user is None:
            return Response({"error": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            app = Application.objects.get(client_id=client_id, client_secret=client_secret)
        except Application.DoesNotExist:
            return Response({"error": "Invalid client_id or client_secret"}, status=status.HTTP_401_UNAUTHORIZED)

        # Generate tokens for the user
        access_token = generate_token()
        refresh_token = generate_token()

        AccessToken.objects.create(
            user=user,
            token=access_token,
            application=app,
            scope=oauth2_settings.DEFAULT_SCOPES,
            expires=timezone.now() + oauth2_settings.ACCESS_TOKEN_EXPIRE_SECONDS
        )

        RefreshToken.objects.create(
            user=user,
            token=refresh_token,
            application=app,
            access_token=AccessToken.objects.get(token=access_token)
        )

        return Response({"access_token": access_token, "refresh_token": refresh_token})


class GoogleLoginView(APIView):
    """
    View for Google login.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated:
            try:
                # Get the OAuth2 Application
                app = Application.objects.get(name="google")
                token = app.accesstoken_set.get(user=user)

                return Response({
                    "access_token": token.token,
                    "expires_in": token.expires
                })

            except Application.DoesNotExist:
                return Response({"error": "OAuth2 Application not found."})

        else:
            return redirect(load_strategy().build_absolute_uri('/social-auth/login/google-oauth2/'))


class UserRegistrationView(generics.CreateAPIView):
    """
    View for user registration.
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    View for user profile retrieval and update.
    """
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        user = serializer.save()
        if 'new_password' in self.request.data:
            new_password = self.request.data['new_password']
            user.set_password(new_password)
            user.save()

            # Send an email to notify the user about the password change
            subject = 'Password Changed'
            message = 'Your password has been changed successfully.'
            recipient = user.email
            send_forgot_password_email.delay(subject, message, recipient)
