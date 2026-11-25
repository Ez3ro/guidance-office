from django.contrib import admin

from .models import InterventionType


@admin.register(InterventionType)
class InterventionTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
