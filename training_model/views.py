from django.http import HttpResponse

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
    file_path = document.file.path
    index_name = document.index_name
    namespace = User.objects.get(pk=request.user.id).username

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

    return HttpResponse("Training complete.")
