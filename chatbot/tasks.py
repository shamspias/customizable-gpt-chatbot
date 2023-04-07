import openai
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

from site_settings.models import SiteSetting

logger = get_task_logger(__name__)

# Get system prompt from site settings
try:
    system_prompt_obj = SiteSetting.objects.first()
    system_prompt = system_prompt_obj.prompt
except Exception as e:
    system_prompt = "You are sonic you can do anything you want."
    logger.error(f"Failed to get system prompt from site settings: {e}")


@shared_task
def send_gpt_request(message_list):
    try:
        openai.api_key = settings.OPENAI_API_KEY
        # Send request to GPT-3 (replace with actual GPT-3 API call)
        gpt3_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                         {"role": "system",
                          "content": system_prompt},
                         {"role": "user", "content": "Who are you?"},
                         {"role": "assistant",
                          "content": "I am the sonic powered by ChatGpt.Contact me sonic@deadlyai.com"},
                     ] + message_list
        )

        assistant_response = gpt3_response["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.error(f"Failed to send request to GPT-3.5: {e}")
        return
    return assistant_response
