import openai
from celery import shared_task
from django.conf import settings
from .models import ConversationHistory


@shared_task
def chatbot_response(user_input):
    openai.api_key = settings.OPEN_AI_KEY
    # todo
    # need to change the prompt with last 10 or 20 conversation target is under 500 token
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
    return [message, user_input]
