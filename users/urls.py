from django.urls import path
from .views import UserRegistrationView, UserProfileView

app_name = 'users'

urlpatterns = [
    # User registration endpoint
    path('register/', UserRegistrationView.as_view(), name='register'),

    # User profile retrieval and update endpoint
    path('profile/', UserProfileView.as_view(), name='profile'),
]
