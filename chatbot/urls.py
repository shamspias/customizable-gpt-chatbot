from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    # List and create conversations
    path('conversations/', views.ConversationListCreate.as_view(), name='conversation-list-create'),
    # Retrieve, update, and delete a specific conversation
    # path('conversations/<int:pk>/', views.ConversationDetail.as_view(), name='conversation-detail'),
    # Favourite a conversation
    path('conversations/<int:pk>/favourite/', views.ConversationFavourite.as_view(), name='conversation-favourite'),
    # Archive a conversation
    path('conversations/<int:pk>/archive/', views.ConversationArchive.as_view(), name='conversation-archive'),

    # Delete a conversation
    path('conversations/<int:pk>/delete/', views.ConversationDelete.as_view(), name='conversation-delete'),
    # List messages in a conversation
    path('conversations/<int:conversation_id>/messages/', views.MessageList.as_view(), name='message-list'),
    # Create a message in a conversation
    path('conversations/<int:conversation_id>/messages/create/', views.MessageCreate.as_view(), name='message-create'),
    # async gpt task
    path('conversations/task/<str:task_id>/', views.GPT3TaskStatus.as_view(), name='gpt_task_status'),
]
