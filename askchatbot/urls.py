from django.urls import path
from .views import ChatbotEndpoint

urlpatterns = [
    path('', ChatbotEndpoint.as_view(), name='chatbot'),

]
