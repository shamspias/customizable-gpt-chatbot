import os
import pickle
import mimetypes
from django.conf import settings
from langchain.document_loaders import (
    CSVLoader,
    UnstructuredWordDocumentLoader,
    PyPDFLoader,
)
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS as BaseFAISS

OPENAI_API_KEY = settings.OPENAI_API_KEY
BASE_DIR = settings.BASE_DIR
MODELS_DIR = os.path.join(BASE_DIR, "models")


class FAISS(BaseFAISS):
    """
    FAISS is a vector store that uses the FAISS library to store and search vectors.
    """

    @classmethod
    def load(cls, file_path):
        with open(file_path, "rb") as f:
            return pickle.load(f)

    def save(self, file_path):
        with open(file_path, "wb") as f:
            pickle.dump(self, f)

    def add_vectors(self, new_embeddings):
        # Assuming self.index is the faiss index instance
        self.index.add(new_embeddings)


def get_loader(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)

    if mime_type == "application/pdf":
        return PyPDFLoader(file_path)
    elif mime_type == "text/csv":
        return CSVLoader(file_path)
    elif mime_type in [
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]:
        return UnstructuredWordDocumentLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {mime_type}")


def build_or_update_faiss_index(file_path, index_name):
    faiss_obj_path = os.path.join(MODELS_DIR, f"{index_name}.pickle")
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    loader = get_loader(file_path)
    pages = loader.load_and_split()

    if os.path.exists(faiss_obj_path):
        faiss_index = FAISS.load(faiss_obj_path)
        new_embeddings = FAISS.from_documents(pages, embeddings, index_name=index_name)
        faiss_index.add_vectors(new_embeddings)
    else:
        faiss_index = FAISS.from_documents(pages, embeddings, index_name=index_name)

    faiss_index.save(faiss_obj_path)
    return faiss_index
