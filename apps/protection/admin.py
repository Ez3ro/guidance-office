"""Only reference lists are editable in the Django admin. Case files are not registered:
administrators manage settings, not confidential records."""

from django.contrib import admin

from .models import ConcernType, ReferralAgency


@admin.register(ConcernType)
class ConcernTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_sensitive", "is_active")
    list_filter = ("category", "is_sensitive", "is_active")


@admin.register(ReferralAgency)
class ReferralAgencyAdmin(admin.ModelAdmin):
    list_display = ("name", "agency_type", "contact_info", "is_active")
    list_filter = ("agency_type", "is_active")
