import openai
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

logger = get_task_logger(__name__)

from .models import Message, Conversation

system_prompt = "This is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very " \
                "friendly.\n\nHuman: Hello, who are you?\nAI: I am an AI created by OpenAI. How can I help you " \
                "today?\n\n"


@shared_task
def send_gpt_request(conversation_id, message_list, last_user_message_id):
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
        logger.error(f"Failed to send request to GPT-3: {e}")
        return

    try:
        # Store GPT response as a message
        message = Message(
            conversation_id=conversation_id,
            content=assistant_response,
            is_from_user=False,
            in_reply_to_id=last_user_message_id
        )
        message.save()

    except ObjectDoesNotExist:
        logger.error(f"Conversation with id {conversation_id} does not exist")
    except Exception as e:
        logger.error(f"Failed to save GPT-3 response as a message: {e}")
