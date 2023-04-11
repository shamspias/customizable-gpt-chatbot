from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from .models import Document


class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'index_name', 'file', 'storage_type', 'is_trained', 'uploaded_at', 'train_button')
    search_fields = ('file', 'index_name', 'storage_type')

    change_form_template = 'admin/training_model/document/change_form.html'

    def train_button(self, obj):
        train_url = reverse('train_view', args=[obj.pk])
        return format_html('<a class="button" href="{}">{}</a>', train_url, "Train")


admin.site.register(Document, DocumentAdmin)
