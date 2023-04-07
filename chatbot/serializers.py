from rest_framework import serializers
from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    """
    Message serializer.
    """

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'content', 'created_at', 'is_from_user']


class ConversationSerializer(serializers.ModelSerializer):
    """
    Conversation serializer.
    """
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'created_at', 'updated_at', 'status', 'messages']
