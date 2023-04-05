from rest_framework import serializers
from .models import SiteSetting, Language, Ad


class LanguageSerializer(serializers.ModelSerializer):
    """
    Serializer for the Language model.
    """

    class Meta:
        model = Language
        fields = ['name', 'code']


class SiteSettingSerializer(serializers.ModelSerializer):
    """
    Serializer for the SiteSetting model.
    """

    class Meta:
        model = SiteSetting
        fields = ['title', 'logo']


class AdSerializer(serializers.ModelSerializer):
    """
    Serializer for the Ad model.
    """

    class Meta:
        model = Ad
        fields = ['title', 'description', 'image']
