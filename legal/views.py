import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.http import require_POST

from .models import LegalOrg, LegalService


def legal_list(request):
    orgs = LegalOrg.objects.filter(is_active=True).prefetch_related("services")
    return render(request, "legal/legal_list.html", {"orgs": orgs})


def legal_detail(request, slug):
    org = get_object_or_404(LegalOrg, slug=slug, is_active=True)
    services = org.services.filter(is_active=True)
    return render(request, "legal/legal_detail.html", {"org": org, "services": services})


@require_POST
def legal_inquiry(request, slug):
    org = get_object_or_404(LegalOrg, slug=slug, is_active=True)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    fio      = (data.get("fio") or "").strip()
    phone    = (data.get("phone") or "").strip()
    situation = (data.get("situation") or "").strip()
    svc_id   = data.get("service_id")

    if not fio or not situation:
        return JsonResponse({"ok": False, "error": "Заполните ФИО и ситуацию"}, status=400)

    svc_name  = ""
    svc_price = ""
    if svc_id:
        try:
            svc = org.services.get(id=int(svc_id), is_active=True)
            svc_name  = svc.name
            price_str = f"{int(svc.price)} сом" if svc.price == svc.price.to_integral() else f"{svc.price.normalize()} сом"
            svc_price = f"{price_str} ({svc.price_note})" if svc.price_note else price_str
        except LegalService.DoesNotExist:
            pass

    # Отправка в Telegram
    token = (getattr(settings, "TG_BOT_TOKEN", "") or getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = org.tg_chat_id.strip()

    if token and chat_id:
        t = timezone.localtime().strftime("%d.%m.%Y %H:%M")
        lines = [
            "⚖️ <b>НОВАЯ ЗАЯВКА — Юридические услуги</b>",
            "",
            f"🏢 <b>{escape(org.name)}</b>",
        ]
        if svc_name:
            lines.append(f"📋 Услуга: <b>{escape(svc_name)}</b>")
        if svc_price:
            lines.append(f"💰 Стоимость: {escape(svc_price)}")
        lines += [
            "",
            f"👤 ФИО: <b>{escape(fio)}</b>",
        ]
        if phone:
            lines.append(f"📞 Телефон: {escape(phone)}")
        lines += [
            "",
            f"📝 Ситуация:\n{escape(situation)}",
            "",
            f"⏰ {t}",
        ]
        text = "\n".join(lines)

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if org.tg_thread_id:
            payload["message_thread_id"] = org.tg_thread_id

        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
                timeout=8,
            )
        except Exception as e:
            print("Legal TG error:", e)

    return JsonResponse({"ok": True})
