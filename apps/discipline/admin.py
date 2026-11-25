from django.contrib import admin

from .models import OffenseType, Sanction


@admin.register(OffenseType)
class OffenseTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "level", "is_bullying", "is_device_related", "is_active")
    list_filter = ("level", "is_active", "is_bullying")
    search_fields = ("code", "name")


@admin.register(Sanction)
class SanctionAdmin(admin.ModelAdmin):
    list_display = ("name", "requires_due_process", "is_active")
    list_filter = ("requires_due_process", "is_active")
