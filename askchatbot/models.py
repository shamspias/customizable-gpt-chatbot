from django.db import models


class ConversationHistory(models.Model):
    """
    To store the conversation history
    """
    conversation_id = models.CharField(max_length=100)
    user_input = models.TextField(blank=True, null=True)
    chatbot_response = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.conversation_id
