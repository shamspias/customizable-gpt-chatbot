from django.contrib import admin
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import redirect
from django.urls import path, reverse_lazy, reverse
from django.utils.html import format_html

from django.contrib.auth import get_user_model
from .models import Document

from .pinecone_helpers import build_or_update_pinecone_index

# from .faiss_helpers import build_or_update_faiss_index


User = get_user_model()


class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'index_name', 'file', 'storage_type', 'is_trained', 'uploaded_at', 'train_button')
    list_filter = ('storage_type', 'is_trained')
    search_fields = ('file', 'index_name', 'storage_type')

    change_form_template = 'admin/training_model/document/change_form.html'

    def train_button(self, obj):
        return format_html('<a class="button" href="{}{}{}">{}</a>', obj.pk, "/change/", "train/", "Train")

    train_button.short_description = 'Train'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/train/', self.admin_site.admin_view(self.train_view),
                 name='training_model_document_train'),
        ]
        return custom_urls + urls

    def response_change(self, request, obj):
        if "_train" in request.POST:
            return HttpResponseRedirect(f"{obj.pk}/train/")
        return super().response_change(request, obj)

    def train_view(self, request, object_id):
        """
        Train the model and create the index
        """
        print('object_id: ', object_id)
        print('Training model...')
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

        change_url = reverse('admin:training_model_document_change', args=[object_id])
        return HttpResponseRedirect(change_url)


admin.site.register(Document, DocumentAdmin)
