from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import ConversationHistory
from .tasks import chatbot_response


def get_conversation_history(conversation_id):
    """
    Retrieve old conversations
    """
    if conversation_id:
        conversation_history = ConversationHistory.objects.filter(conversation_id=conversation_id)
    else:
        conversation_history = None
    return conversation_history


class ChatbotEndpoint(APIView):
    """
    APIView for chatbot return task ID for celery
    """

    def post(self, request):
        """
        Send the data to chatbot
        example:
        {
            "user_input": "Hey there! how are you"
        }
        """
        user_input = request.data.get('user_input')
        if user_input is None:
            return Response({"error": "No input values"})

        # todo
        # need to get last 10 or 20 conversation and pass to chatbot response
        task = chatbot_response.apply_async(args=[user_input])
        return Response({"task_id": task.id})

    def get(self, request, format=None):
        """
        Retrieve the data from conversation history

        example:
        URL/chatbot?task_id=task_id

        """
        task_id = request.GET.get('task_id')
        if task_id is None:
            return Response({"error": "No Task ID"})

        # return response from openAI and the user input as a List
        response = chatbot_response.AsyncResult(task_id).get()

        # conversation_obj = ConversationHistory.objects.get_or_create(user=request.user)
        try:
            last_conversation = ConversationHistory.objects.filter(user=request.user).latest('conversation_id')
            conversation_id = last_conversation.conversation_id
            conversation_id += 1
        except:
            conversation_id = 0

        if response[0]:
            conversation = ConversationHistory.objects.create(user=request.user, conversation_id=conversation_id,
                                                              user_input=response[1], chatbot_response=response[0])
            conversation.save()
        return Response({"data": response[0]})
