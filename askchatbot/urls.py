from django.urls import path
from .views import ChatbotEndpoint

urlpatterns = [
    path('chatbot/', ChatbotEndpoint.as_view(), name='chatbot'),

]
