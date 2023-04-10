import pickle
import os

from langchain.vectorstores import FAISS as FISS
from langchain.chat_models import ChatOpenAI
from langchain.schema import (
    SystemMessage,
    HumanMessage,
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


chat = ChatOpenAI(temperature=0, openai_api_key=settings.OPENAI_API_KEY)


class FAISS(FISS):
    """
    FAISS is a vector store that uses the FAISS library to store and search vectors.
    """

    def save(self, file_path):
        with open(file_path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(file_path):
        with open(file_path, "rb") as f:
            return pickle.load(f)


def get_faiss_index(index_name):
    faiss_obj_path = os.path.join(settings.BASE_DIR, "models", "{}.pickle".format(index_name))

    if os.path.exists(faiss_obj_path):
        # Load the FAISS object from disk
        try:
            faiss_index = FAISS.load(faiss_obj_path)
            return faiss_index
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            return None


@shared_task
def send_gpt_request(message_list):
    try:
        # Load the FAISS index
        faiss_index = get_faiss_index("buffer_salaries")

        if faiss_index:
            # Add extra text to the content of the last message
            last_message = message_list[-1]

            # Get the most similar documents to the last message
            try:
                docs = faiss_index.similarity_search(query=last_message.content, k=2)

                updated_content = last_message.content + "\n\n"
                for doc in docs:
                    updated_content += doc.page_content + "\n\n"
            except Exception as e:
                logger.error(f"Failed to get similar documents: {e}")
                updated_content = last_message.content

            # Create a new HumanMessage object with the updated content
            updated_message = HumanMessage(content=updated_content)

            # Replace the last message in message_list with the updated message
            message_list[-1] = updated_message

        messages = [
                       SystemMessage(content=system_prompt)
                   ] + message_list

        assistant_response = chat(messages).content

    except Exception as e:
        logger.error(f"Failed to send request to GPT-3.5: {e}")
        return
    return assistant_response
