from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .serializers import UserRegistrationSerializer, UserProfileSerializer
from .tasks import send_forgot_password_email
from django.contrib.auth import get_user_model

User = get_user_model()


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
