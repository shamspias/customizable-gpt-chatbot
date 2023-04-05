from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .serializers import UserRegistrationSerializer, UserProfileSerializer
from .tasks import send_forgot_password_email
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from social_django.utils import load_strategy
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from oauth2_provider.models import Application

User = get_user_model()


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
