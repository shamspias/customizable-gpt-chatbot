from django.contrib import admin

from .models import ConversationHistory, ChatbotBasic, Language, Ads, ChatbotSuggestions, ChatbotSuggestionsOptions


class ConversationHistoryAdmin(admin.ModelAdmin):
    """
    Model admin for conversation
    """
    list_display = ('user', 'conversation_id', 'user_input', 'chatbot_response', 'created_at')
    list_filter = ('user', 'conversation_id',)
    search_fields = ('user_input', 'chatbot_response', 'user')


@admin.register(ChatbotBasic)
class ChatbotBasicAdmin(admin.ModelAdmin):
    list_display = ('name', 'logo', 'short_logo', 'back_ground')


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name')


@admin.register(Ads)
class AdsAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'ads_image')


@admin.register(ChatbotSuggestions)
class ChatbotSuggestionsAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(ChatbotSuggestionsOptions)
class ChatbotSuggestionsOptionsAdmin(admin.ModelAdmin):
    list_display = ('name',)


admin.site.register(ConversationHistory, ConversationHistoryAdmin)
