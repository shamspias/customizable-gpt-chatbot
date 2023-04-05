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
