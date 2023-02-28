from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import speech_recognition as sr
from django.conf import settings

from .models import ConversationHistory
from .tasks import chatbot_response, get_rasa_response

RASA_API = settings.RASA_API_URL


def get_conversation_history(conversation_id):
    """
    Retrieve old conversations
    """
    if conversation_id:
        conversation_history = ConversationHistory.objects.filter(conversation_id=conversation_id)
    else:
        conversation_history = None
    return conversation_history


class ConversationalHistory(APIView):
    """
    APIView to get all the conversational history from a user
    """

    def get(self, request):
        conversations = ConversationHistory.objects.filter(user=request.user).order_by('-created_at')
        data = []
        for conversation in conversations:
            data.append({
                "user_message": conversation.user_input,
                "bot_response": conversation.chatbot_response,
                "createdAt": conversation.created_at,
                "conversation_id": conversation.conversation_id,
            })
        return Response({"data": data}, status=status.HTTP_200_OK)


class DeleteConversationalHistory(APIView):
    """
    API View to delete all the conversation history
    """

    def get(self, request):
        ConversationHistory.objects.filter(user=request.user).delete()
        return Response({"message": "Deleted"}, status=status.HTTP_200_OK)


class ChatbotEndpoint(APIView):
    """
    APIView for chatbot return task ID for celery
    """

    def post(self, request):
        """
        Send the data to chatbot
        example:
        {
            "user_input": "Hey there! how are you",
            "language": "English"
        }
        """
        user_input = request.data.get('user_input')
        language = request.data.get('language', "English")
        if user_input is None:
            return Response({"error": "No input values"})

        # get last 15 conversation and pass to chatbot response
        chatbot_prompt = ""
        conversations = ConversationHistory.objects.filter(user=request.user).order_by('-created_at')[:15]
        for conversation in conversations:
            if conversation.user_input is None:
                conversation.user_input = ""
            if conversation.chatbot_response is None:
                conversation.chatbot_response = ""
            chatbot_prompt += "user:" + conversation.user_input + "\nbot:" + conversation.chatbot_response + "\n"

        chatbot_prompt += "user:" + user_input + "\nbot:"

        # save the user input into database
        try:
            last_conversation = ConversationHistory.objects.filter(user=request.user).latest('conversation_id')
            conversation_id = last_conversation.conversation_id
            conversation_id += 1
        except:
            conversation_id = 0
        if user_input:
            conversation = ConversationHistory.objects.create(user=request.user, conversation_id=conversation_id,
                                                              user_input=user_input)
            conversation.save()

        try:
            task = get_rasa_response.apply_async(args=[user_input, conversation_id, language, chatbot_prompt])
            return Response({"task_id": task.id}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            task = chatbot_response.apply_async(args=[chatbot_prompt, conversation_id, language])
            return Response({"task_id": task.id}, status=status.HTTP_200_OK)

    def get(self, request, format=None):
        """
        Retrieve the data from conversation history

        example:
        URL/chatbot?task_id=task_id

        """
        task_id = request.GET.get('task_id')
        if task_id is None:
            return Response({"error": "No Task ID"})

        # return response from openAI and the user input as a List
        try:
            response = get_rasa_response.AsyncResult(task_id).get()
        except Exception as e:
            print(e)
            response = chatbot_response.AsyncResult(task_id).get()

        print(response)
        if response[0] is None:
            response[0] = ""

        elif response[0] == "lf":
            task = chatbot_response.apply_async(args=[response[2], response[1], response[3]])
            response = task.get()

        conversation_obj = ConversationHistory.objects.get(user=request.user, conversation_id=response[1])
        conversation_obj.chatbot_response = response[0]
        conversation_obj.save()

        return Response({"data": response[0]}, status=status.HTTP_200_OK)


class SpeechToText(APIView):
    """
    API View to Voice to Text
    """

    def post(self, request):
        try:
            recognizer = sr.Recognizer()
            # audio_file = sr.AudioData(request.body, sample_rate=44100, sample_width=2,
            # endpoint=sr.AudioFile.AudioData)
            audio_file = sr.AudioData(request.body, sample_rate=44100, sample_width=2)
            text = recognizer.recognize_google(audio_file)

            return Response({'text': text})
        except sr.UnknownValueError:
            return Response({'error': 'Speech recognition could not understand the audio'}, status=400)
        except sr.RequestError as e:
            return Response({'error': f'Speech recognition error: {e}'}, status=500)
