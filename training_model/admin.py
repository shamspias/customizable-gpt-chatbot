from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.contrib.auth import get_user_model
from .models import Document

from .pinecone_helpers import build_or_update_pinecone_index

# from .faiss_helpers import build_or_update_faiss_index


User = get_user_model()


class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'index_name', 'file', 'storage_type', 'is_trained', 'uploaded_at')
    list_filter = ('storage_type', 'is_trained')
    search_fields = ('file', 'index_name', 'storage_type')

    change_form_template = 'admin/training_model/document/change_form.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/train/', self.admin_site.admin_view(self.train_view), name='train'),
        ]
        return custom_urls + urls

    def response_change(self, request, obj):
        if "_train" in request.POST:
            return HttpResponseRedirect(f"../{obj.pk}/train/")
        return super().response_change(request, obj)

    def train_view(self, request, object_id):
        document = Document.objects.get(pk=object_id)
        file_path = document.file.path
        index_name = document.index_name
        namespace = User.objects.get(pk=request.user.id).username

        # Load and process files`

        # FAISS
        # build_or_update_faiss_index(file_path, index_name)
        # self.message_user(request, 'Training complete. The FAISS index has been created.')

        # Pinecone
        build_or_update_pinecone_index(file_path, index_name, namespace)
        self.message_user(request, 'Training complete. The Pinecone index has been created.')

        return HttpResponseRedirect("../")


admin.site.register(Document, DocumentAdmin)
