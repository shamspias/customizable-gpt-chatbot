import os
import uuid
from django.db import models


def upload_to_faiss(instance, filename):
    basename, ext = os.path.splitext(filename)
    new_filename = f"{basename}_{uuid.uuid4().hex}{ext}"
    return f'documents/faiss/{new_filename}'


def upload_to_pinecone(instance, filename):
    basename, ext = os.path.splitext(filename)
    new_filename = f"{basename}_{uuid.uuid4().hex}{ext}"
    return f'documents/pinecone/{new_filename}'


def dynamic_upload_to(instance, filename):
    if instance.storage_type == 'FAISS':
        return upload_to_faiss(instance, filename)
    else:
        return upload_to_pinecone(instance, filename)


class Document(models.Model):
    CHOICES = (
        ('FAISS', 'FAISS'),
        ('PINECONE', 'PINECONE')
    )

    file = models.FileField(upload_to=dynamic_upload_to)
    index_name = models.CharField(max_length=255)
    storage_type = models.CharField(max_length=255, choices=CHOICES)
    trained = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name
