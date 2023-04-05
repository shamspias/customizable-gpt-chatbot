from rest_framework import generics
from .models import SiteSetting, Language, Ad
from .serializers import SiteSettingSerializer, LanguageSerializer, AdSerializer


class SiteSettingList(generics.ListAPIView):
    """
    API view to list SiteSettings.
    """
    queryset = SiteSetting.objects.all()
    serializer_class = SiteSettingSerializer


class LanguageList(generics.ListAPIView):
    """
    API view to list available Languages.
    """
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer


class AdList(generics.ListAPIView):
    """
    API view to list Ads.
    """
    queryset = Ad.objects.all()
    serializer_class = AdSerializer
