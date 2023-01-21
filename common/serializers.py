from django.conf import settings
from rest_framework.serializers import ImageField as ApiImageField
from easy_thumbnails.files import get_thumbnailer

THUMBNAIL_ALIASES = getattr(settings, 'THUMBNAIL_ALIASES', {})


def get_url(request, instance, alias_obj, alias=None):
    if alias is not None:
        return request.build_absolute_uri(get_thumbnailer(instance).get_thumbnail(alias_obj[alias]).url)
    elif alias is None:
        return request.build_absolute_uri(instance.url)
    else:
        raise TypeError('Unsupported field type')


def image_sizes(request, instance, alias_obj):
    i_sizes = list(alias_obj.keys())
    return {'original': get_url(request, instance, alias_obj),
            **{k: get_url(request, instance, alias_obj, k) for k in i_sizes}}


class ThumbnailerJSONSerializer(ApiImageField):
    def __init__(self, alias_target, **kwargs):
        self.alias_target = THUMBNAIL_ALIASES.get(alias_target)
        super(ThumbnailerJSONSerializer, self).__init__(**kwargs)

    def to_representation(self, instance):
        if instance:
            return image_sizes(self.context['request'], instance, self.alias_target)
        return None
