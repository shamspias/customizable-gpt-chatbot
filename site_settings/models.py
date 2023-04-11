from django.db import models


class Language(models.Model):
    """
    Language model representing available languages.
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)

    class Meta:
        verbose_name_plural = "Languages"

    def __str__(self):
        return self.name


class SiteSetting(models.Model):
    """
    SiteSetting model representing website settings.
    """
    title = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='site_logo/')
    prompt = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return self.title


class Ad(models.Model):
    """
    Ad model representing advertisements.
    """
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='ads/')

    class Meta:
        verbose_name_plural = "Ads"

    def __str__(self):
        return self.title


class PineconeIndex(models.Model):
    """
    PineconeIndex model representing pinecone indexes.
    """
    name = models.CharField(max_length=200)
    index_id = models.CharField(max_length=200)

    class Meta:
        verbose_name_plural = "Pinecone Indexes"

    def __str__(self):
        return self.name


class DefaultSettings(models.Model):
    """
    DefaultSettings model representing default settings.
    """
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    site_setting = models.ForeignKey(SiteSetting, on_delete=models.CASCADE)
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "Default Settings"

    def __str__(self):
        return f"Default Settings"
