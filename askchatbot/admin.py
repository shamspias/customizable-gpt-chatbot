from django.contrib import admin
from .models import Conversation, Message, FavoriteConversation


class MessageInline(admin.TabularInline):
    """
    Inline admin class to display messages within a conversation.
    """
    model = Message
    extra = 0
    readonly_fields = ('text', 'is_user', 'created_at')


class ConversationAdmin(admin.ModelAdmin):
    """
    Admin class for Conversation model.
    """
    list_display = ('id', 'created_at', 'is_archived')
    list_filter = ('is_archived',)
    search_fields = ('id',)
    inlines = [MessageInline]


class MessageAdmin(admin.ModelAdmin):
    """
    Admin class for Message model.
    """
    list_display = ('id', 'conversation', 'text', 'is_user', 'created_at')
    list_filter = ('is_user',)
    search_fields = ('text', 'conversation__id')


class FavoriteConversationAdmin(admin.ModelAdmin):
    """
    Admin class for FavoriteConversation model.
    """
    list_display = ('id', 'conversation', 'created_at')
    search_fields = ('conversation__id',)


admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(FavoriteConversation, FavoriteConversationAdmin)
