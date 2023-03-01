from rest_framework import serializers
from .models import ConversationHistory, ChatbotBasic, Language, Ads, ChatbotSuggestions, ChatbotSuggestionsOptions


class ConversationHistorySerializer(serializers.ModelSerializer):
    """
    Serializer to keep conversation history
    """

    class Meta:
        model = ConversationHistory
        fields = ('conversation_id', 'user_input', 'chatbot_response', 'timestamp')


class ChatbotBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotBasic
        fields = '__all__'


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = '__all__'


class AdsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ads
        fields = '__all__'


class ChatbotSuggestionsOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatbotSuggestionsOptions
        fields = '__all__'


class ChatbotSuggestionsSerializer(serializers.ModelSerializer):
    options = ChatbotSuggestionsOptionsSerializer(many=True)

    class Meta:
        model = ChatbotSuggestions
        fields = '__all__'
