from django.db import models
from django.contrib.auth.models import User


class Conversation(models.Model):
    """
    Conversation model representing a chat conversation.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    def __str__(self):
        return f"Conversation {self.id} - {self.user.username}"


class Message(models.Model):
    """
    Message model representing a message within a conversation.
    """
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_from_user = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Message {self.id} - {self.conversation}"
