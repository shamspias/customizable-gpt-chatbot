from django.urls import path
from . import views

urlpatterns = [
    path('conversations/', views.ConversationList.as_view(), name='conversation-list'),
    path('conversations/<int:pk>/', views.ConversationDetail.as_view(), name='conversation-detail'),
    path('conversations/<int:pk>/messages/', views.MessageList.as_view(), name='message-list'),
    path('conversations/<int:pk>/archive/', views.ArchiveConversation.as_view(), name='archive-conversation'),
    path('favorites/', views.FavoriteConversationList.as_view(), name='favorite-conversation-list'),
    path('favorites/<int:pk>/', views.FavoriteConversationDetail.as_view(), name='favorite-conversation-detail'),
]
