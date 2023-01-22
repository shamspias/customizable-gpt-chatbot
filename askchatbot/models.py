from django.db import models
from ausers.models import User


class ConversationHistory(models.Model):
    """
    To store the conversation history
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    conversation_id = models.CharField(max_length=100, unique=True)
    user_input = models.TextField(blank=True, null=True)
    chatbot_response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.conversation_id
