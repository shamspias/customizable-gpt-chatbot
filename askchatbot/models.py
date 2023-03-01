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
        return self.user.email

    def last_conversation_id(self):
        """
        to retrieve the last conversation id
        """
        try:
            last_conversation = self.objects.latest('conversation_id')
            return last_conversation.conversation_id
        except self.DoesNotExist:
            return None


class ChatbotBasic(models.Model):
    """
    Model to set chatbot basic settings
    """
    name = models.CharField(max_length=250, blank=True, null=True)
    logo = models.FileField(upload_to="logo/", null=True)
    short_logo = models.FileField(upload_to='short_logo/', null=True)
    back_ground = models.FileField(upload_to='media/', null=True)

    def __str__(self):
        return self.name


class Language(models.Model):
    """
    Language selection
    """
    name = models.CharField(max_length=250, blank=True, null=True)
    short_name = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name


class Ads(models.Model):
    """
    To manage Ads
    """
    name = models.CharField(max_length=250, blank=True, null=True)
    description = models.CharField(max_length=250, blank=True, null=True)
    ads_image = models.FileField(upload_to='ads/', null=True)

    class Meta:
        verbose_name = "Ads"
        verbose_name_plural = "Ads"

    def __str__(self):
        return self.name


class ChatbotSuggestionsOptions(models.Model):
    """
    Information and suggestions Options
    """
    name = models.CharField(max_length=250, blank=True, null=True)


class ChatbotSuggestions(models.Model):
    """
    Information and suggestions
    """
    name = models.CharField(max_length=250, blank=True, null=True)
    options = models.ManyToManyField(ChatbotSuggestionsOptions, related_name='chatbot')

    class Meta:
        verbose_name = "Chatbot Suggestion"
        verbose_name_plural = "Chatbot Suggestions"

    def __str__(self):
        return self.name
