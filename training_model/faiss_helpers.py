import os
import pickle
import mimetypes
from langchain.document_loaders.csv_loader import CSVLoader
from langchain.document_loaders import UnstructuredWordDocumentLoader
from langchain.document_loaders import PyPDFLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS as FISS
from django.conf import settings

embeddings = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)


class FAISS(FISS):
    """
    FAISS is a vector store that uses the FAISS library to store and search vectors.
    """

    def save(self, file_path):
        with open(file_path, "wb") as f:
            pickle.dump(self, f)


def get_loader(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)

    if mime_type == 'application/pdf':
        return PyPDFLoader(file_path)
    elif mime_type == 'text/csv':
        return CSVLoader(file_path)
    elif mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        return UnstructuredWordDocumentLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {mime_type}")


def build_or_update_faiss_index(file_path, index_name):
    faiss_obj_path = os.path.join(settings.BASE_DIR, "models", "{}.pickle".format(index_name))

    loader = get_loader(file_path)
    pages = loader.load_and_split()

    if os.path.exists(faiss_obj_path):
        # Load the FAISS object from disk
        with open(faiss_obj_path, "rb") as f:
            faiss_index = pickle.load(f)

        # make new embeddings
        new_embeddings = FAISS.from_documents(pages, embeddings, index_name=index_name)

        # Add the new embeddings to the existing index
        faiss_index.add(new_embeddings)
        faiss_index.save(faiss_obj_path)
    else:
        # Build and save the FAISS object

        faiss_index = FAISS.from_documents(pages, embeddings, index_name=index_name)
        faiss_index.save(faiss_obj_path)

    return faiss_index
