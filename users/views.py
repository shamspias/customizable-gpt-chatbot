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
from datetime import timedelta
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

        if username is None or password is None or client_id is None:
            return Response({"error": "username, password and client_id are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if user is None:
            return Response({"error": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            app = Application.objects.get(client_id=client_id)
        except Application.DoesNotExist:
            return Response({"error": "Invalid client_id"}, status=status.HTTP_401_UNAUTHORIZED)

        # Generate tokens for the user
        access_token = generate_token()
        refresh_token = generate_token()
        expires_in = timedelta(seconds=oauth2_settings.ACCESS_TOKEN_EXPIRE_SECONDS)
        expires = timezone.now() + expires_in

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
        context = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            # "expires_in": expires_in.total_seconds()
        }

        return Response(context, status=status.HTTP_200_OK)


class GoogleLoginView(APIView):
    """
    View for Google login.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated:
            try:
                # Get the OAuth2 Application
                app = Application.objects.get(name="google")
                access_token = app.accesstoken_set.get(user=user)
                refresh_token = RefreshToken.objects.get(user=user, access_token=access_token)

                context = {
                    "access_token": access_token.token,
                    "refresh_token": refresh_token.token
                    # "expires_in": access_token.expires
                }

                return Response(context, status=status.HTTP_200_OK)

            except Application.DoesNotExist:
                return Response({"error": "OAuth2 Application not found."}, status=status.HTTP_404_NOT_FOUND)

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


class LogoutView(APIView):
    """
    View for user logout.
    """

    def post(self, request, *args, **kwargs):
        token = request.auth
        if token:
            access_token = AccessToken.objects.filter(token=token)
            if access_token.exists():
                access_token.delete()
                return Response({"detail": "Logout successful"}, status=status.HTTP_200_OK)

        return Response({"detail": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
