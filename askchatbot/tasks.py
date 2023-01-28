import openai
from celery import shared_task
from django.conf import settings
from .models import ConversationHistory


@shared_task
def chatbot_response(chatbot_prompt, conversation_id):
    openai.api_key = settings.OPEN_AI_KEY
    # todo
    # need to change the prompt with last 10 or 20 conversation target is under 500 token
    prompt = f"{chatbot_prompt}"
    completions = openai.Completion.create(
        engine="text-davinci-003",
        prompt="Conversational friendly chatbot\n" + prompt,
        max_tokens=1024,
        n=1,
        stop="user",
        temperature=0.9,
    )
    message = completions.choices[0].text
    return [message, conversation_id]
