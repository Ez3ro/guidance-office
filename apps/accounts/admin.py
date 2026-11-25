from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "is_cpc_member", "is_active")
    list_filter = ("role", "is_cpc_member", "is_active")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email", "position")}),
        ("Access", {"fields": ("role", "is_cpc_member", "is_active", "must_change_password")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"fields": ("username", "role", "password1", "password2")}),)

    def has_delete_permission(self, request, obj=None):
        return False  # deactivate instead, so the audit trail stays intact
