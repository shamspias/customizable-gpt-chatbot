from django.contrib import admin

from .models import ConversationHistory


class ConversationHistoryAdmin(admin.ModelAdmin):
    """
    Model admin for conversation
    """
    list_display = ('user', 'conversation_id', 'user_input', 'chatbot_response', 'created_at')
    list_filter = ('user', 'conversation_id',)
    search_fields = ('user_input', 'chatbot_response', 'user')


admin.site.register(ConversationHistory, ConversationHistoryAdmin)
