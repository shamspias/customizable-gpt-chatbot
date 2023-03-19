from rest_framework import serializers
from .models import Conversation, Message, FavoriteConversation


class MessageSerializer(serializers.ModelSerializer):
    """
    Message Serializer for chatbot
    """

    class Meta:
        model = Message
        fields = ['text', 'is_user', 'created_at']


class ConversationSerializer(serializers.ModelSerializer):
    """
    Conversation Serializers for chatbot
    """
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'created_at', 'is_archived', 'messages']


class FavoriteConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for favorite conversations
    """
    conversation = ConversationSerializer()

    class Meta:
        model = FavoriteConversation
        fields = ['id', 'conversation', 'created_at']
