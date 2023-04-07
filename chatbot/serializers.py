from rest_framework import serializers
from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    """
    Message serializer.
    """

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'content', 'is_from_user', 'in_reply_to', 'created_at', ]


class ConversationSerializer(serializers.ModelSerializer):
    """
    Conversation serializer.
    """
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'favourite', 'archive', 'created_at', 'messages']
