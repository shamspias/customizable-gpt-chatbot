from rest_framework.views import APIView
from rest_framework.response import Response

from .models import ConversationHistory
from .tasks import chatbot_response


class ChatbotEndpoint(APIView):
    """
    APIView for chatbot return task ID for celery
    """

    def post(self, request):
        user_input = request.data.get('user_input')
        conversation_id = request.data.get('conversation_id', 1)
        if user_input is None:
            return Response({"error": "No input values"})
        task = chatbot_response.apply_async(args=[user_input, conversation_id])
        return Response({"task_id": task.id})

    def get(self, request, format=None):
        task_id = request.GET.get('task_id')
        if task_id is None:
            return Response({"error": "No Task ID"})
        response = chatbot_response.AsyncResult(task_id).get()
        return Response({"data": response})


def get_conversation_history(conversation_id):
    conversation_history = ConversationHistory.objects.filter(conversation_id=conversation_id)
    return conversation_history
