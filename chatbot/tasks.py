import pickle
import os
import openai
# from langchain.vectorstores import FAISS as BaseFAISS
from training_model.pinecone_helpers import (
    PineconeManager,
    PineconeIndexManager,
    embeddings,
)
from langchain.vectorstores import Pinecone
from langchain.embeddings import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.schema import (
    SystemMessage,
    HumanMessage,
    AIMessage,
)

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

PINECONE_API_KEY = settings.PINECONE_API_KEY
PINECONE_ENVIRONMENT = settings.PINECONE_ENVIRONMENT
PINECONE_INDEX_NAME = settings.PINECONE_INDEX_NAME
OPENAI_API_KEY = settings.OPENAI_API_KEY

chat = ChatOpenAI(temperature=0, openai_api_key=OPENAI_API_KEY)
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)


#
# class FAISS(BaseFAISS):
#     """
#     FAISS is a vector store that uses the FAISS library to store and search vectors.
#     """
#
#     def save(self, file_path):
#         with open(file_path, "wb") as f:
#             pickle.dump(self, f)
#
#     @staticmethod
#     def load(file_path):
#         with open(file_path, "rb") as f:
#             return pickle.load(f)

#
# def get_faiss_index(index_name):
#     faiss_obj_path = os.path.join(settings.BASE_DIR, "models", "{}.pickle".format(index_name))
#
#     if os.path.exists(faiss_obj_path):
#         # Load the FAISS object from disk
#         try:
#             faiss_index = FAISS.load(faiss_obj_path)
#             return faiss_index
#         except Exception as e:
#             logger.error(f"Failed to load FAISS index: {e}")
#             return None

def get_pinecone_index(index_name, name_space):
    pinecone_manager = PineconeManager(PINECONE_API_KEY, PINECONE_ENVIRONMENT)
    pinecone_index_manager = PineconeIndexManager(pinecone_manager, index_name)

    try:
        pinecone_index = Pinecone.from_existing_index(index_name=pinecone_index_manager.index_name,
                                                      embedding=embeddings)
        # pinecone_index = Pinecone.from_existing_index(index_name=pinecone_index_manager.index_name,
        #                                               namespace=name_space, embedding=embeddings)
        return pinecone_index

    except Exception as e:
        logger.error(f"Failed to load Pinecone index: {e}")
        return None


@shared_task
def send_gpt_request(message_list, name_space):
    try:

        # new_messages_list = []
        # for msg in message_list:
        #     if msg["role"] == "user":
        #         new_messages_list.append(HumanMessage(content=msg["content"]))
        #     else:
        #         new_messages_list.append(AIMessage(content=msg["content"]))
        # Load the FAISS index
        # base_index = get_faiss_index("buffer_salaries")

        # Load the Pinecone index
        base_index = get_pinecone_index(PINECONE_INDEX_NAME, name_space)

        if base_index:
            # Add extra text to the content of the last message
            last_message = message_list[-1]

            # Get the most similar documents to the last message
            try:
                docs = base_index.similarity_search(query=last_message["content"], k=2)

                updated_content = last_message["content"] + "\n\n"
                for doc in docs:
                    updated_content += doc.page_content + "\n\n"
            except Exception as e:
                logger.error(f"Failed to get similar documents: {e}")
                updated_content = last_message.content

            # Create a new HumanMessage object with the updated content
            # updated_message = HumanMessage(content=updated_content)
            updated_message = {"role": "user", "content": updated_content}

            # Replace the last message in message_list with the updated message
            message_list[-1] = updated_message

        openai.api_key = settings.OPENAI_API_KEY
        # Send request to GPT-3 (replace with actual GPT-3 API call)
        gpt3_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                         {"role": "system",
                          "content": system_prompt},
                     ] + message_list
        )

        assistant_response = gpt3_response["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.error(f"Failed to send request to GPT-3.5: {e}")
        return "Sorry, I'm having trouble understanding you."
    return assistant_response


@shared_task
def generate_title_request(message_list):
    try:
        openai.api_key = settings.OPENAI_API_KEY
        # Send request to GPT-3 (replace with actual GPT-3 API call)
        gpt3_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                         {"role": "system",
                          "content": "Summarize and make a very short meaningful title under 55 characters"},
                     ] + message_list
        )
        response = gpt3_response["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.error(f"Failed to send request to GPT-3.5: {e}")
        return "Problematic title with error."
    return response
