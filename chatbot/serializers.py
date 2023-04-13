from rest_framework import serializers

from .models import Conversation, Message
from .utils import time_since


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
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'favourite', 'archive', 'created_at', 'messages']

    def get_created_at(self, obj):
        return time_since(obj.created_at)
