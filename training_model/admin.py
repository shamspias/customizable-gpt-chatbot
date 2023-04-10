from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from .models import Document
from .faiss_helpers import build_faiss_index


class DocumentAdmin(admin.ModelAdmin):
    change_form_template = 'admin/your_app_name/document/change_form.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('train/', self.admin_site.admin_view(self.train_view), name='train'),
        ]
        return custom_urls + urls

    def response_change(self, request, obj):
        if "_train" in request.POST:
            return HttpResponseRedirect("train/")
        return super().response_change(request, obj)

    def train_view(self, request):
        # Load and process files
        build_faiss_index()

        self.message_user(request, 'Training complete. The FAISS index has been created.')
        return HttpResponseRedirect("../")


admin.site.register(Document, DocumentAdmin)
