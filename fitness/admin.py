from django.contrib import admin

from .models import (ClubStaff, Expense, FitnessClub, Lead, LeadNote, Member,
                     Membership, MembershipPlan, Payment, Section, Trainer,
                     TrainerBooking, TrainerSchedule, Visit)


class StaffInline(admin.TabularInline):
    model = ClubStaff
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(FitnessClub)
class FitnessClubAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "is_active", "tg_leads_chat_id", "tg_gym_chat_id")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [StaffInline]


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "club", "phone", "card_id", "is_active")
    list_filter = ("club", "is_active")
    search_fields = ("full_name", "phone", "card_id")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "member", "plan", "start_date", "end_date",
                    "remaining_visits", "debt_amount", "is_active", "is_frozen")
    list_filter = ("is_active", "is_frozen", "plan__club")
    search_fields = ("member__full_name", "member__phone")


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "club", "price_per_session", "is_active")
    list_filter = ("club", "is_active")
    search_fields = ("name",)
    filter_horizontal = ("sections",)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "phone", "club", "status", "source", "next_contact_at")
    list_filter = ("club", "status", "source")
    search_fields = ("name", "phone")


@admin.register(TrainerBooking)
class TrainerBookingAdmin(admin.ModelAdmin):
    list_display = ("id", "trainer", "date", "time_from", "who", "status")
    list_filter = ("club", "status", "date")
    search_fields = ("client_name", "phone", "member__full_name")


for model in (Section, MembershipPlan, TrainerSchedule, Visit, Payment, Expense,
              LeadNote, ClubStaff):
    admin.site.register(model)
