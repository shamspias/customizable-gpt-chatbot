from celery import shared_task
import openai

from .models import Message

system_prompt = "This is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very " \
                "friendly.\n\nHuman: Hello, who are you?\nAI: I am an AI created by OpenAI. How can I help you " \
                "today?\n\n"


@shared_task
def send_gpt_request(conversation_id, message_list):
    """
    Task to send request to GPT-3.5 or upper and store the response as a message.
    """
    # Send request to GPT-3.5 (replace with actual GPT-3 API call)
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

    # Store GPT response as a message
    message = Message(
        conversation_id=conversation_id,
        content=gpt3_response["choices"][0]["message"]["content"].strip(),
        is_from_user=False
    )
    message.save()
