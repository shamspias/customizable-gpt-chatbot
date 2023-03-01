from django.urls import path
from .views import (
    ChatbotEndpoint,
    ConversationalHistory,
    DeleteConversationalHistory,
    SpeechToText,
    ChatbotBasicListCreateAPIView,
    LanguageListCreateAPIView,
    AdsListCreateAPIView,
    ChatbotSuggestionsListCreateAPIView
)

urlpatterns = [
    path('', ChatbotEndpoint.as_view(), name='chatbot'),
    path('history/', ConversationalHistory.as_view(), name='conversations'),
    path('history/delete/', DeleteConversationalHistory.as_view(), name='conversations-delete'),
    # path('speech-to-text/', SpeechToText.as_view(), name='conversations-voice'),
    path('chatbot-basics/', ChatbotBasicListCreateAPIView.as_view(), name='chatbot_basic_list_create'),
    path('languages/', LanguageListCreateAPIView.as_view(), name='language_list_create'),
    path('ads/', AdsListCreateAPIView.as_view(), name='ads_list_create'),
    path('chatbot-suggestions/', ChatbotSuggestionsListCreateAPIView.as_view(), name='chatbot_suggestions_list_create'),
]
