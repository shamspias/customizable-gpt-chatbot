import openai
import requests
import json
from celery import shared_task
from django.conf import settings

RASA_API = settings.RASA_API_URL


@shared_task
def chatbot_response(chatbot_prompt, conversation_id, language):
    openai.api_key = settings.OPEN_AI_KEY
    prompt = f"{chatbot_prompt}"
    completions = openai.Completion.create(
        engine="text-davinci-003",
        prompt="Customer support chatbot talk in " + language + "\n" + prompt,
        max_tokens=1024,
        n=1,
        stop="user",
        temperature=0.9,
    )
    message = completions.choices[0].text
    return [message, conversation_id]


@shared_task
def get_rasa_response(message, conversation_id, language, chatbot_prompt):
    url = RASA_API
    # data = {'sender': 'user', 'message': message}
    payload = json.dumps({
        "sender": "test_user",
        "message": message
    })
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            json_response = response.json()
            if json_response and len(json_response) > 0:
                first_response = json_response[0]
                confidence = first_response.get('confidence', 0.0)
                if confidence >= 0.5:
                    replay = first_response.get('text', 'no answer')
                    return [replay, conversation_id]
                else:
                    return ["lc", conversation_id, chatbot_prompt, language]  # less confidante
            else:
                return ["error", conversation_id, chatbot_prompt, language,
                        "Not get json response: response: {} url:{}".format(response.text, url)]
        else:
            return ["error", conversation_id, chatbot_prompt, language, "error status code"]
    except Exception as e:
        print(e)
        return ["error", conversation_id, chatbot_prompt, language, str(e)]  # error to fetch API
