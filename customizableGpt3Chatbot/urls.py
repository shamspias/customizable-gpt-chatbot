from django.conf import settings
from django.urls import path, re_path, include
from django.conf.urls.static import static
from django.contrib import admin
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from ausers.urls import users_router

schema_view = get_schema_view(
    openapi.Info(
        title="Custom chatbot API",
        default_version='v1',
        description="API for custom chatbot",
        terms_of_service="https://github.com/shamspias",
        contact=openapi.Contact(email="shamspias0@gmail.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny, ],
)

router = DefaultRouter()

router.registry.extend(users_router.registry)

urlpatterns = [
                  # admin panel
                  path('admin/', admin.site.urls),

                  # api
                  path('api/v1/', include(router.urls)),

                  # Chatbot
                  path('api/v1/chatbot/', include('askchatbot.urls'), name="chatbot"),  # chatbot

                  # auth
                  path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
                  path('api/v1/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
                  path('api/v1/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
                  path('api/v1/auth/logout/', TokenBlacklistView.as_view(), name='token_blacklisted'),

                  # swagger docs
                  re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0),
                          name='schema-json'),
                  path('', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
                  path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Admin Site Config
admin.sites.AdminSite.site_header = settings.ADMIN_SITE_HEADER
admin.sites.AdminSite.site_title = settings.ADMIN_SITE_TITLE
admin.sites.AdminSite.index_title = settings.ADMIN_SITE_INDEX
