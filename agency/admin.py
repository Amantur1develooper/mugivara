from django.contrib import admin
from .models import Agency, AgencyService, AgencyMembership


class AgencyServiceInline(admin.TabularInline):
    model = AgencyService
    extra = 0


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [AgencyServiceInline]


@admin.register(AgencyMembership)
class AgencyMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "agency")
