import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.http import require_POST

from .models import Agency, AgencyService


def agency_list(request):
    agencies = Agency.objects.filter(is_active=True).prefetch_related("services")
    return render(request, "agency/agency_list.html", {"agencies": agencies})


def agency_detail(request, slug):
    agency = get_object_or_404(Agency, slug=slug, is_active=True)
    services = agency.services.filter(is_active=True)
    return render(request, "agency/agency_detail.html", {"agency": agency, "services": services})


@require_POST
def agency_inquiry(request, slug):
    agency = get_object_or_404(Agency, slug=slug, is_active=True)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    name     = (data.get("name") or "").strip()
    phone    = (data.get("phone") or "").strip()
    message  = (data.get("message") or "").strip()
    svc_id   = data.get("service_id")

    if not name or not message:
        return JsonResponse({"ok": False, "error": "Заполните имя и описание задачи"}, status=400)

    svc_name  = ""
    svc_price = ""
    if svc_id:
        try:
            svc = agency.services.get(id=int(svc_id), is_active=True)
            svc_name  = svc.name
            price_str = f"{int(svc.price)} сом" if svc.price else "по договорённости"
            svc_price = f"{price_str} ({svc.price_note})" if svc.price_note else price_str
        except AgencyService.DoesNotExist:
            pass

    token   = (getattr(settings, "TG_BOT_TOKEN", "") or getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = agency.tg_chat_id.strip()

    if token and chat_id:
        t = timezone.localtime().strftime("%d.%m.%Y %H:%M")
        lines = [
            "💻 <b>НОВАЯ ЗАЯВКА — IT Агентство</b>",
            "",
            f"🏢 <b>{escape(agency.name)}</b>",
        ]
        if svc_name:
            lines.append(f"🛠 Услуга: <b>{escape(svc_name)}</b>")
        if svc_price:
            lines.append(f"💰 Стоимость: {escape(svc_price)}")
        lines += [
            "",
            f"👤 Имя: <b>{escape(name)}</b>",
        ]
        if phone:
            lines.append(f"📞 Телефон: {escape(phone)}")
        lines += [
            "",
            f"📝 Задача:\n{escape(message)}",
            "",
            f"⏰ {t}",
        ]
        text = "\n".join(lines)

        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if agency.tg_thread_id:
            payload["message_thread_id"] = agency.tg_thread_id

        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
                timeout=8,
            )
        except Exception as e:
            print("Agency TG error:", e)

    return JsonResponse({"ok": True})
