from django.db import models


def upload_to_faiss(instance, filename):
    return 'documents/faiss/{0}'.format(filename)


def upload_to_pinecone(instance, filename):
    return 'documents/pinecone/{0}'.format(filename)


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
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name
