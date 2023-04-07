from django.contrib import admin
from .models import SiteSetting, Language, Ad


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    """
    Admin site configuration for Language model.
    """
    list_display = ('name', 'code',)
    search_fields = ('name', 'code',)


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    """
    Admin site configuration for SiteSetting model.
    """
    list_display = ('title', 'logo', 'prompt',)
    search_fields = ('title',)


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    """
    Admin site configuration for Ad model.
    """
    list_display = ('title', 'description', 'image',)
    search_fields = ('title', 'description',)
