from django.contrib import admin
from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Admin site configuration for Conversation model.
    """
    list_display = ('conversation_id', 'user', 'created_at', 'updated_at', 'status')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Admin site configuration for Message model.
    """
    list_display = ('id', 'conversation', 'content', 'is_from_user', 'created_at')
    list_filter = ('is_from_user', 'conversation__user__username', 'created_at')
    search_fields = ('content',)
    ordering = ('-created_at',)
