import openai
from celery import Celery
from django.conf import settings
from .models import ConversationHistory


@Celery.task
def chatbot_response(user_input, conversation_id):
    openai.api_key = settings
    prompt = f"{user_input}"
    completions = openai.Completion.create(
        engine="text-davinci-002",
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
