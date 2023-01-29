from django.urls import path
from .views import ChatbotEndpoint, ConversationalHistory

urlpatterns = [
    path('', ChatbotEndpoint.as_view(), name='chatbot'),
    path('history/', ConversationalHistory.as_view(), name='conversations'),

]
