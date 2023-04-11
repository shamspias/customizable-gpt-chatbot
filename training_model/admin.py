from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.html import format_html
from django.contrib.auth import get_user_model
from .models import Document

from .pinecone_helpers import build_or_update_pinecone_index

# from .faiss_helpers import build_or_update_faiss_index


User = get_user_model()


class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'index_name', 'file', 'storage_type', 'is_trained', 'uploaded_at', 'train_button')
    search_fields = ('file', 'index_name', 'storage_type')

    change_form_template = 'admin/training_model/document/change_form.html'

    def train_button(self, obj):
        return format_html('<a class="button" href="{}">{}</a>', f"{obj.pk}/change/train/", "Train")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/change/train/', self.admin_site.admin_view(self.train_view), name='train'),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['train_url'] = f'{object_id}/train/'
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def response_change(self, request, obj):
        if "train" in request.POST:
            self.train_view(request, obj)
            return HttpResponseRedirect("../")
        return super().response_change(request, obj)

    def train_view(self, request, object_id):
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
        self.message_user(request, 'Training complete. The Pinecone index has been created.')

        return HttpResponseRedirect("../")


admin.site.register(Document, DocumentAdmin)
