from django.test import TestCase, Client
from django.urls import reverse
import json

from .models import ConversationHistory


class ChatbotTestCase(TestCase):
    """
    test for chatbot
    """

    def setUp(self):
        self.client = Client()

    def test_chatbot_endpoint(self):
        conversation_id = "123456"
        user_input = "Hello"
        response = self.client.post(reverse('chatbot'),
                                    data={'user_input': user_input, 'conversation_id': conversation_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {'task_id': '123'})

        conversation = ConversationHistory.objects.get(conversation_id=conversation_id)
        self.assertEqual(conversation.user_input, user_input)
        self.assertEqual(conversation.chatbot_response, "Hi!")
