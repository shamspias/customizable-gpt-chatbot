from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from .models import Conversation, Message, FavoriteConversation


class ChatGPTAPITestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()

        self.conversation = Conversation.objects.create()
        self.message1 = Message.objects.create(conversation=self.conversation, text="Hello", is_user=True)
        self.message2 = Message.objects.create(conversation=self.conversation, text="Hi there!", is_user=False)

        self.favorite_conversation = FavoriteConversation.objects.create(conversation=self.conversation)

    def test_create_conversation(self):
        url = reverse('conversation-list')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_conversations(self):
        url = reverse('conversation-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_conversation_detail(self):
        url = reverse('conversation-detail', args=[self.conversation.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_message(self):
        url = reverse('message-list', args=[self.conversation.id])
        data = {"text": "What's the weather like today?"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_messages(self):
        url = reverse('message-list', args=[self.conversation.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_archive_conversation(self):
        url = reverse('archive-conversation', args=[self.conversation.id])
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_create_favorite_conversation(self):
        new_conversation = Conversation.objects.create()
        url = reverse('favorite-conversation-list')
        data = {"conversation": new_conversation.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_favorite_conversations(self):
        url = reverse('favorite-conversation-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_favorite_conversation_detail(self):
        url = reverse('favorite-conversation-detail', args=[self.favorite_conversation.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_favorite_conversation(self):
        url = reverse('favorite-conversation-detail', args=[self.favorite_conversation.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
