from django.db import models


def upload_to_faiss(filename):
    return 'documents/faiss/{0}'.format(filename)


def upload_to_pinecone(filename):
    return 'documents/pinecone/{0}'.format(filename)


class Document(models.Model):
    CHOICES = (
        ('FAISS', 'FAISS'),
        ('PINECONE', 'PINECONE')
    )

    file = models.FileField(upload_to=upload_to_pinecone)
    index_name = models.CharField(max_length=255)
    storage_type = models.CharField(max_length=255, choices=CHOICES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.storage_type == 'FAISS':
            self.file.upload_to = upload_to_faiss
        else:
            self.file.upload_to = upload_to_pinecone
        super().save(*args, **kwargs)

    def __str__(self):
        return self.file.name
