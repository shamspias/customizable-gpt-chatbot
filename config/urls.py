from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf import settings

schema_view = get_schema_view(
    openapi.Info(
        title="Customized ChatGPT API",
        default_version='v1',
        description="API documentation for the Customized ChatGPT project",
    ),
    public=True,
    permission_classes=[permissions.AllowAny, ],
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # OAuth2 provider URLs
    path('oauth2/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    # Social auth URLs
    path('social-auth/', include('social_django.urls', namespace='social')),

    # Rest framework URLs
    path('api-auth/', include('rest_framework.urls')),

    # Users app URLs
    path('api/v1/users/', include('users.urls')),

    # Site settings app URLs
    path('api/v1/site-settings/', include('site_settings.urls')),

    # Chatbot app URLs
    path('api/v1/chatbot/', include('chatbot.urls')),

    # Swagger URLs
    path('', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_TITLE
admin.site.index_title = settings.ADMIN_SITE_INDEX
