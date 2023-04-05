from rest_framework import serializers
from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for the Message model.
    """

    class Meta:
        model = Message
        fields = ['content', 'created_at', 'is_from_user']


class ConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for the Conversation model.
    """
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'created_at', 'updated_at', 'is_active', 'is_archived', 'messages']
