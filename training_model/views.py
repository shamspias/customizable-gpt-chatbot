from django.http import HttpResponse
import requests
import tempfile
import os
from django.contrib.auth import get_user_model
from .models import Document

from .pinecone_helpers import build_or_update_pinecone_index

# from .faiss_helpers import build_or_update_faiss_index


User = get_user_model()


def train_view(request, object_id):
    document = Document.objects.get(pk=object_id)
    print(object_id)
    print('------------------')

    document = Document.objects.get(pk=object_id)
    index_name = document.index_name
    namespace = User.objects.get(pk=request.user.id).username

    # Download the file and save it to a temporary directory
    file_url = document.file.url
    response = requests.get(file_url)
    temp_dir = tempfile.mkdtemp()
    file_name = os.path.join(temp_dir, os.path.basename(file_url))

    with open(file_name, 'wb') as f:
        f.write(response.content)

    file_path = file_name
    # Load and process files`

    # FAISS
    # build_or_update_faiss_index(file_path, index_name)
    # self.message_user(request, 'Training complete. The FAISS index has been created.')

    # Pinecone
    print(object_id)
    print('------------------')
    print(file_path, index_name, namespace)
    print('------------------')
    build_or_update_pinecone_index(file_path, index_name, namespace)

    # Remember to clean up the temporary directory after you're done
    os.remove(file_path)
    os.rmdir(temp_dir)

    return HttpResponse("Training complete.")
