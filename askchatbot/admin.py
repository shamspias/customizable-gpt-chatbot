from django.contrib import admin

from .models import ConversationHistory


class ConversationHistoryAdmin(admin.ModelAdmin):
    list_display = ('conversation_id', 'user_input', 'chatbot_response', 'timestamp')
    list_filter = ('conversation_id',)
    search_fields = ('user_input', 'chatbot_response')


admin.site.register(ConversationHistory, ConversationHistoryAdmin)
