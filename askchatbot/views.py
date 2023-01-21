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
        conversation_id = request.data.get('conversation_id')
        task = chatbot_response.apply_async(args=[user_input, conversation_id])
        return Response({"task_id": task.id})


def get_conversation_history(conversation_id):
    conversation_history = ConversationHistory.objects.filter(conversation_id=conversation_id)
    return conversation_history
