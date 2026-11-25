from django.contrib import admin

from .models import Enrollment, SchoolYear, Section, Student


@admin.register(SchoolYear)
class SchoolYearAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_current")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "grade_level", "school_year", "adviser")
    list_filter = ("school_year", "grade_level")
    search_fields = ("name",)
    autocomplete_fields = ("adviser",)


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    autocomplete_fields = ("section",)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """Basic enrolment data only; confidential guidance fields are deliberately excluded."""

    list_display = ("last_name", "first_name", "lrn", "sex", "status")
    list_filter = ("status", "sex")
    search_fields = ("last_name", "first_name", "lrn")
    exclude = Student.CONFIDENTIAL_FIELDS + ("created_by", "updated_by")
    inlines = [EnrollmentInline]

    def has_delete_permission(self, request, obj=None):
        return False
