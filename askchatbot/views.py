from django.views import View
from django.http import JsonResponse
import openai
from .tasks import chatbot_response


class ChatbotView(View):
    """
    View for chatbot return task ID for celery
    """

    def post(self, request):
        user_input = request.POST.get('user_input')
        conversation_id = request.POST.get('conversation_id')
        task = chatbot_response.apply_async(args=[user_input, conversation_id])
        return JsonResponse({"task_id": task.id})
