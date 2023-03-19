from django.db import models


class Conversation(models.Model):
    """
    Model for Conversation and check archive or not
    """
    created_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False)


class Message(models.Model):
    """
    Model for conversation message and get from user
    """
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    text = models.TextField()
    is_user = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)


class FavoriteConversation(models.Model):
    """
    Model to add favorite conversation
    """
    conversation = models.OneToOneField(Conversation, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
