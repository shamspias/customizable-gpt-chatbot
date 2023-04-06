from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from .tasks import send_gpt_request


class LastMessagesPagination(LimitOffsetPagination):
    """
    Pagination class for last messages.
    """
    default_limit = 10
    max_limit = 10


# List and create conversations
class ConversationListCreate(generics.ListCreateAPIView):
    """
    List and create conversations.
    """
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# Retrieve, update, and delete a specific conversation
class ConversationDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, and delete a specific conversation.
    """
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        conversation = self.get_object()
        if conversation.user != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        return super().delete(request, *args, **kwargs)


# Archive a conversation
class ConversationArchive(APIView):
    """
    Archive a conversation.
    """

    def patch(self, request, pk):
        conversation = get_object_or_404(Conversation, id=pk, user=request.user)
        conversation.status = 'archived'
        conversation.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# End a conversation
class ConversationEnd(APIView):
    """
    End a conversation.
    """

    def patch(self, request, pk):
        conversation = get_object_or_404(Conversation, id=pk, user=request.user)
        conversation.status = 'ended'
        conversation.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# Delete a conversation
class ConversationDelete(APIView):
    """
    Delete a conversation.
    """

    def delete(self, request, pk):
        conversation = get_object_or_404(Conversation, id=pk, user=request.user)
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# List messages in a conversation
class MessageList(generics.ListAPIView):
    """
    List messages in a conversation.
    """
    serializer_class = MessageSerializer
    pagination_class = LastMessagesPagination

    def get_queryset(self):
        conversation = get_object_or_404(Conversation, id=self.kwargs['conversation_id'], user=self.request.user)
        return Message.objects.filter(conversation=conversation).select_related('conversation')


# Create a message in a conversation
class MessageCreate(generics.CreateAPIView):
    """
    Create a message in a conversation.
    """
    serializer_class = MessageSerializer

    def perform_create(self, serializer):
        conversation = get_object_or_404(Conversation, id=self.kwargs['conversation_id'], user=self.request.user)
        serializer.save(conversation=conversation, is_from_user=True)

        # Retrieve the last 10 messages from the conversation
        messages = Message.objects.filter(conversation=conversation).order_by('-created_at')[:10][::-1]

        # Build the list of dictionaries containing the message data
        message_list = [
            {
                "role": "user" if msg.is_from_user else "assistant",
                "content": msg.content
            }
            for msg in messages
        ]

        # Call the Celery task to get a response from GPT-3
        send_gpt_request.delay(conversation.id, message_list)
