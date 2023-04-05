from django.contrib import admin
from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Admin site configuration for Conversation model.
    """
    list_display = ('id', 'user', 'created_at', 'updated_at', 'is_active', 'is_archived')
    search_fields = ('user__username',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Admin site configuration for Message model.
    """
    list_display = ('id', 'conversation', 'content', 'created_at', 'is_from_user')
    search_fields = ('conversation__id', 'content',)
    list_filter = ('is_from_user', 'user__username',)
    ordering = ('-created_at',)
