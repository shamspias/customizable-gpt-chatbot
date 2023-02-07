from django.urls import path
from .views import ChatbotEndpoint, ConversationalHistory, DeleteConversationalHistory, SpeechToText

urlpatterns = [
    path('', ChatbotEndpoint.as_view(), name='chatbot'),
    path('history/', ConversationalHistory.as_view(), name='conversations'),
    path('history/delete/', DeleteConversationalHistory.as_view(), name='conversations-delete'),
    path('speech-to-text/', SpeechToText.as_view(), name='conversations-voice'),

]
