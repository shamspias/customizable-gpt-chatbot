from rest_framework import serializers
from .models import Conversation, Message


class ConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for Conversation model.
    """

    class Meta:
        model = Conversation
        fields = ('id', 'created_at', 'status')


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for Message model.
    """

    class Meta:
        model = Message
        fields = ('id', 'conversation', 'content', 'is_from_user', 'created_at')
