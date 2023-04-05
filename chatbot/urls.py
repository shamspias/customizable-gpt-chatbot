from django.urls import path
from .views import ConversationListCreate, ConversationDetail, MessageCreate, MessageList

app_name = 'chatbot'

urlpatterns = [
    # Conversations list and create endpoint
    path('conversations/', ConversationListCreate.as_view(), name='conversations-list-create'),

    # Conversation detail, update, and delete endpoint
    path('conversations/<int:pk>/', ConversationDetail.as_view(), name='conversation-detail'),

    # Message create endpoint
    path('conversations/<int:conversation_id>/messages/', MessageCreate.as_view(), name='message-create'),

    # Last 10 messages list endpoint
    path('conversations/<int:conversation_id>/messages/last10/', MessageList.as_view(), name='messages-last10'),
]
