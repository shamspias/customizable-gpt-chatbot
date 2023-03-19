from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from .models import Conversation, Message, FavoriteConversation
from .serializers import ConversationSerializer, MessageSerializer, FavoriteConversationSerializer
from .tasks import chatbot_response


class ConversationList(generics.ListCreateAPIView):
    """
    This view allows listing all the conversations or creating a new one.
    """
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer


class ConversationDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    This view allows retrieving, updating, or deleting a conversation.
    """
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer


class MessageList(generics.ListCreateAPIView):
    """
    This view allows listing all the messages in a conversation or creating a new one
    with a user input and generating a response from GPT-3.
    """
    serializer_class = MessageSerializer

    def get_queryset(self):
        conversation = get_object_or_404(Conversation, pk=self.kwargs['pk'])
        return Message.objects.filter(conversation=conversation)

    def perform_create(self, serializer):
        conversation = get_object_or_404(Conversation, pk=self.kwargs['pk'])
        user_input = serializer.validated_data['text']
        language = serializer.validated_data['language']

        # Call GPT-3 API
        gpt_output = chatbot_response(user_input, language)
        serializer.save(conversation=conversation, is_user=True)
        Message.objects.create(conversation=conversation, text=gpt_output, is_user=False)


class FavoriteConversationList(generics.ListCreateAPIView):
    """
    This view allows listing all the favorite conversations or adding a new one.
    """
    queryset = FavoriteConversation.objects.all()
    serializer_class = FavoriteConversationSerializer


class FavoriteConversationDetail(generics.RetrieveDestroyAPIView):
    """
    This view allows retrieving or deleting a favorite conversation.
    """
    queryset = FavoriteConversation.objects.all()
    serializer_class = FavoriteConversationSerializer


class ArchiveConversation(generics.UpdateAPIView):
    """
    This view allows archiving or unarchiving a conversation.
    """
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer

    def patch(self, request, *args, **kwargs):
        conversation = self.get_object()
        conversation.is_archived = not conversation.is_archived
        conversation.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
