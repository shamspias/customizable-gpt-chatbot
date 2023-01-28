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
        """
        task_id = request.GET.get('task_id')
        if task_id is None:
            return Response({"error": "No Task ID"})

        # return response from openAI and the user input as a List
        response = chatbot_response.AsyncResult(task_id).get()

        try:
            conversation_obj = ConversationHistory.objects.filter(user=request.user).latest()
        except:
            conversation_obj = ConversationHistory.objects.create(user=request.user)

        conversation_id = conversation_obj.conversation_id
        if conversation_id is None:
            conversation_id = 0
        else:
            conversation_id += 1

        if response[0]:
            conversation_obj.conversation_id = conversation_id,
            conversation_obj.user_input = response[1],
            conversation_obj.chatbot_response = response[0],

            conversation_obj.save()
        return Response({"data": response[0]})
