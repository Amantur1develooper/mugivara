from django.contrib import admin

from .models import SurveyResponse


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ("restaurant_name", "phone", "score", "created_at")
    list_filter = ("score",)
    search_fields = ("restaurant_name", "phone", "q1", "q2", "q3", "q4")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
