from rest_framework import generics, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from .tasks import send_gpt_request


class ConversationListCreate(generics.ListCreateAPIView):
    """
    API view to list and create Conversations.
    """
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ConversationDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a Conversation.
    """
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer


class MessageCreate(generics.CreateAPIView):
    """
    API view to create a Message.
    """
    queryset = Message.objects.all()
    serializer_class = MessageSerializer

    def perform_create(self, serializer):
        conversation = get_object_or_404(Conversation, id=self.kwargs['conversation_id'])
        serializer.save(conversation=conversation)
        send_gpt_request.delay(conversation.id, serializer.validated_data['content'])


class MessageList(generics.ListAPIView):
    """
    API view to list the last 10 messages of a Conversation.
    """
    serializer_class = MessageSerializer

    def get_queryset(self):
        conversation = get_object_or_404(Conversation, id=self.kwargs['conversation_id'])
        return Message.objects.filter(conversation=conversation)[:10]
