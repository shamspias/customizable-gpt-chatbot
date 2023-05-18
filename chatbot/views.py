from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from celery.result import AsyncResult
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import get_user_model

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from .tasks import send_gpt_request, generate_title_request

User = get_user_model()


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
        return Conversation.objects.filter(user=self.request.user).order_by('created_at')

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
        if conversation.archive:
            conversation.archive = False
            conversation.save()
            return Response({"message": "remove from archive"}, status=status.HTTP_200_OK)
        else:
            conversation.archive = True
            conversation.save()
            return Response({"message": "add to archive"}, status=status.HTTP_200_OK)


class ConversationFavourite(APIView):
    """
    Favourite a conversation.
    """

    def patch(self, request, pk):
        conversation = get_object_or_404(Conversation, id=pk, user=request.user)
        if conversation.favourite:
            conversation.favourite = False
            conversation.save()
            return Response({"message": "remove from favourite"}, status=status.HTTP_200_OK)
        else:
            conversation.favourite = True
            conversation.save()
            return Response({"message": "add to favourite"}, status=status.HTTP_200_OK)


# Delete a conversation
class ConversationDelete(APIView):
    """
    Delete a conversation.
    """

    def delete(self, request, pk):
        conversation = get_object_or_404(Conversation, id=pk, user=request.user)
        conversation.delete()
        return Response({"message": "conversation deleted"}, status=status.HTTP_200_OK)


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
        message_list = []
        for msg in messages:
            if msg.is_from_user:
                message_list.append({"role": "user", "content": msg.content})
            else:
                message_list.append({"role": "assistant", "content": msg.content})

        # message_list = []
        # for msg in messages:
        #     if msg.is_from_user:
        #         message_list.append(HumanMessage(content=msg.content))
        #     else:
        #         message_list.append(AIMessage(content=msg.content))

        name_space = User.objects.get(id=self.request.user.id).username

        from site_settings.models import SiteSetting
        # Get system prompt from site settings
        try:
            system_prompt_obj = SiteSetting.objects.first()
            system_prompt = system_prompt_obj.prompt
        except Exception as e:
            print(str(e))
            system_prompt = "You are sonic you can do anything you want."

        # Call the Celery task to get a response from GPT-3
        task = send_gpt_request.apply_async(args=(message_list, name_space, system_prompt))
        print(message_list)
        response = task.get()
        return [response, conversation.id, messages[0].id]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_list = self.perform_create(serializer)
        assistant_response = response_list[0]
        conversation_id = response_list[1]
        last_user_message_id = response_list[2]

        try:
            # Store GPT response as a message
            message = Message(
                conversation_id=conversation_id,
                content=assistant_response,
                is_from_user=False,
                in_reply_to_id=last_user_message_id
            )
            message.save()

        except ObjectDoesNotExist:
            error = f"Conversation with id {conversation_id} does not exist"
            Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            error_mgs = str(e)
            error = f"Failed to save GPT-3 response as a message: {error_mgs}"
            Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        headers = self.get_success_headers(serializer.data)
        return Response({"response": assistant_response}, status=status.HTTP_200_OK, headers=headers)


class ConversationRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """
    Retrieve View to update or get the title
    """
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    lookup_url_kwarg = 'conversation_id'

    def retrieve(self, request, *args, **kwargs):
        conversation = self.get_object()

        if conversation.title == "Empty":
            messages = Message.objects.filter(conversation=conversation)

            if messages.exists():
                message_list = []
                for msg in messages:
                    if msg.is_from_user:
                        message_list.append({"role": "user", "content": msg.content})
                    else:
                        message_list.append({"role": "assistant", "content": msg.content})

                task = generate_title_request.apply_async(args=(message_list,))
                my_title = task.get()
                # if length of title is greater than 55, truncate it
                my_title = my_title[:30]
                conversation.title = my_title
                conversation.save()
                serializer = self.get_serializer(conversation)
                return Response(serializer.data)
            else:
                return Response({"message": "No messages in conversation."}, status=status.HTTP_204_NO_CONTENT)
        else:
            serializer = self.get_serializer(conversation)
            return Response(serializer.data)


class GPT3TaskStatus(APIView):
    """
    Check the status of a GPT task and return the result if it's ready.
    """

    def get(self, request, task_id, *args, **kwargs):
        task = AsyncResult(task_id)

        if task.ready():
            response = task.result
            return Response({"status": "READY", "response": response})
        else:
            return Response({"status": "PENDING"})
