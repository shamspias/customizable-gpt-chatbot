from rest_framework import serializers
from .models import ConversationHistory


class ConversationHistorySerializer(serializers.ModelSerializer):
    """
    Serializer to keep conversation history
    """

    class Meta:
        model = ConversationHistory
        fields = ('conversation_id', 'user_input', 'chatbot_response', 'timestamp')
