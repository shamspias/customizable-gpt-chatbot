from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import ConversationHistory


@admin.register(ConversationHistory)
class ConversationHistoryAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('conversation_id', 'user_input')}),
        (
            _('Personal info'),
            {
                'fields': (
                    'conversation_id',
                    'user_input',
                    'chatbot_response',
                    'timestamp',
                )
            },
        ),
        (_('Conversation ID'), {'fields': ('conversation_id',)}),
        (_('User Input'), {'fields': ('user_input',)}),
        (_('Response'), {'fields': ('chatbot_response', 'timestamp')}),
    )
