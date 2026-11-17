from django import forms
from django.contrib import admin

from .models import (AutosalonTelegramRecipient, BranchTelegramLink,
                     ShopTelegramRecipient, TelegramRecipient)


# ── Понятная ошибка вместо «уже существует» ─────────────────────────────────

def _recipient_form(owner_field):
    """Форма получателя: объясняет, что именно мешает сохранить.

    Django на дубле писал «Telegram recipient с такими значениями полей
    Branch и Chat id уже существует» — из этого не видно ни что делать, ни
    того, что один чат можно подключить дважды в разные темы форума.
    """

    class RecipientForm(forms.ModelForm):
        class Meta:
            fields = "__all__"

        def clean(self):
            cleaned = super().clean()
            owner = cleaned.get(owner_field)
            chat_id = (cleaned.get("chat_id") or "").strip()
            thread = cleaned.get("message_thread_id")
            if not (owner and chat_id):
                return cleaned

            # Проверяем сами: в базе NULL не равен NULL, поэтому два
            # получателя без темы ограничение в базе не поймало бы.
            twin = (self._meta.model.objects
                    .filter(**{owner_field: owner}, chat_id=chat_id,
                            message_thread_id=thread)
                    .exclude(pk=self.instance.pk)
                    .first())
            if twin:
                where = f", тема {thread}" if thread else ""
                raise forms.ValidationError(
                    f"Этот чат уже подключён к «{owner}»{where} — запись №{twin.id} "
                    f"«{twin.title or twin.chat_id}». Откройте её, чтобы поменять "
                    f"настройки. А чтобы слать ещё и в другую тему той же группы, "
                    f"укажите её Topic ID."
                )
            return cleaned

    return RecipientForm


class BranchTelegramLinkInline(admin.TabularInline):
    model = BranchTelegramLink
    extra = 0
    autocomplete_fields = ("recipient",)
    fields = ("recipient", "notify_orders", "notify_bookings")


@admin.register(TelegramRecipient)
class TelegramRecipientAdmin(admin.ModelAdmin):
    form = _recipient_form("branch")
    list_display = ("id", "branch", "title", "kind", "chat_id",
                    "message_thread_id", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("title", "chat_id")


@admin.register(ShopTelegramRecipient)
class ShopTelegramRecipientAdmin(admin.ModelAdmin):
    form = _recipient_form("branch")
    list_display = ("id", "branch", "title", "kind", "chat_id",
                    "message_thread_id", "is_active", "notify_new_orders")
    list_filter = ("kind", "is_active")
    search_fields = ("title", "chat_id", "branch__name_ru")
    autocomplete_fields = ("branch",)


@admin.register(AutosalonTelegramRecipient)
class AutosalonTelegramRecipientAdmin(admin.ModelAdmin):
    form = _recipient_form("dealership")
    list_display = ("id", "dealership", "title", "kind", "chat_id",
                    "message_thread_id", "is_active", "notify_new_leads")
    list_filter = ("kind", "is_active")
    search_fields = ("title", "chat_id", "dealership__name")
    autocomplete_fields = ("dealership",)
