from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {"fields": ("phone_number", "address", "profile_picture")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'address', 'profile_picture')
        }),
    )


admin.site.register(CustomUser, CustomUserAdmin)
