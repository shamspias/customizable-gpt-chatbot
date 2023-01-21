from django.urls import path
from .views import ChatbotView

urlpatterns = [
    path('chatbot/', ChatbotView.as_view(), name='chatbot'),
]
