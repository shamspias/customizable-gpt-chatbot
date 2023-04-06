from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from .tasks import send_gpt_request


class LastMessagesPagination(LimitOffsetPagination):
    """
    Pagination class to return the last messages.
    """
    default_limit = 10
    max_limit = 10


class ConversationListCreate(generics.ListCreateAPIView):
    """
    List all conversations or create a new one.
    """
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ConversationDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a conversation instance.
    """
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        conversation = self.get_object()
        if conversation.user != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        return super().delete(request, *args, **kwargs)


class MessageList(generics.ListAPIView):
    """
    List the last 10 messages of a conversation.
    """
    serializer_class = MessageSerializer
    pagination_class = LastMessagesPagination

    def get_queryset(self):
        conversation = get_object_or_404(Conversation, id=self.kwargs['conversation_id'], user=self.request.user)
        return Message.objects.filter(conversation=conversation).select_related('conversation')


class MessageCreate(generics.CreateAPIView):
    """
    Create a new message.
    """
    serializer_class = MessageSerializer

    def perform_create(self, serializer):
        conversation = get_object_or_404(Conversation, id=self.kwargs['conversation_id'], user=self.request.user)
        serializer.save(conversation=conversation, is_from_user=True)

        # Call the Celery task to get a response from GPT-3
        send_gpt_request.delay(conversation.id, serializer.validated_data['content'])
