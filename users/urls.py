from django.urls import path
from .views import UserRegistrationView, UserProfileView, GoogleLoginView

app_name = 'users'

urlpatterns = [
    # User registration endpoint
    path('register/', UserRegistrationView.as_view(), name='register'),

    # User profile retrieval and update endpoint
    path('profile/', UserProfileView.as_view(), name='profile'),

    # Google OAuth2 login endpoint
    path('login/google/', GoogleLoginView.as_view(), name='google-login'),
]
