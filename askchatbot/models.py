from django.db import models
from ausers.models import User


class ConversationHistory(models.Model):
    """
    To store the conversation history
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    conversation_id = models.PositiveIntegerField(default=0)
    user_input = models.TextField(blank=True, null=True)
    chatbot_response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.user

    def last_conversation_id(self):
        """
        to retrieve the last conversation id
        """
        try:
            last_conversation = self.objects.latest('conversation_id')
            return last_conversation.conversation_id
        except self.DoesNotExist:
            return None
