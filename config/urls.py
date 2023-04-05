from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # OAuth2 provider URLs
    path('oauth2/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    # Social auth URLs
    path('social-auth/', include('social_django.urls', namespace='social')),

    # Users app URLs
    path('users/', include('users.urls', namespace='users')),
]
