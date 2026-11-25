from django.contrib import admin

from .models import SchoolProfile


@admin.register(SchoolProfile)
class SchoolProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "school_id", "division", "region")

    def has_add_permission(self, request):
        return not SchoolProfile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
