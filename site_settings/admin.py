from django.contrib import admin
from .models import SiteSetting, Language, Ad, PineconeIndex, DefaultSettings


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


@admin.register(PineconeIndex)
class PineconeIndexAdmin(admin.ModelAdmin):
    """
    Admin site configuration for PineconeIndex model.
    """
    list_display = ('name', 'index_id',)
    search_fields = ('name', 'index_id',)


@admin.register(DefaultSettings)
class DefaultSettingsAdmin(admin.ModelAdmin):
    """
    Admin site configuration for DefaultSettings model.
    """
    list_display = ('language', 'site_setting', 'ad',)
    search_fields = ('language', 'site_setting', 'ad',)
