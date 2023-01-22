import openai
from celery import shared_task
from django.conf import settings
from .models import ConversationHistory


@shared_task
def chatbot_response(user_input, conversation_id):
    openai.api_key = settings.OPEN_AI_KEY
    prompt = f"{user_input}"
    completions = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=1024,
        n=1,
        stop=None,
        temperature=0.5,
    )
    message = completions.choices[0].text
    conversation_history = ConversationHistory(
        conversation_id=conversation_id,
        user_input=user_input,
        chatbot_response=message
    )
    conversation_history.save()
    return message
