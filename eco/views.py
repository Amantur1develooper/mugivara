import json
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import EcoProject, EcoService, EcoApplication


def _tg_bot_token():
    return (getattr(settings, "TG_BOT_TOKEN", "") or
            getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def _notify_new_application(app):
    """Отправляет новую эко-заявку в Telegram-группу проекта."""
    token = _tg_bot_token()
    chat_id = (app.project.tg_chat_id or "").strip()
    if not token or not chat_id:
        return
    created = timezone.localtime(app.created_at).strftime("%d.%m.%Y %H:%M")
    lines = [
        "♻️ <b>Новая эко-заявка</b>",
        f"🏢 Проект: {escape(app.project.name)}",
        f"🧾 Услуга: {escape(app.service_name or '—')}",
        "",
        f"👤 {escape(app.fio)}",
    ]
    if app.phone:
        lines.append(f"📞 {escape(app.phone)}")
    lines.append(f"📍 {escape(app.address)}")
    if app.comment:
        lines.append(f"📝 {escape(app.comment)}")
    lines.append(f"⏰ {created}")
    payload = {
        "chat_id": chat_id,
        "text": "\n".join(lines),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if app.project.tg_thread_id:
        payload["message_thread_id"] = app.project.tg_thread_id
    try:
        import requests as req
        req.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=8)
    except Exception:
        pass


def eco_list(request):
    projects = EcoProject.objects.filter(is_active=True).prefetch_related("services")
    return render(request, "eco/eco_list.html", {"projects": projects})


def eco_detail(request, slug):
    project  = get_object_or_404(EcoProject, slug=slug, is_active=True)
    services = project.services.filter(is_active=True)
    return render(request, "eco/eco_detail.html", {"project": project, "services": services})


@require_POST
def eco_apply(request, slug):
    """Сохраняет заявку в БД. Вызывается из JS перед открытием WhatsApp."""
    project = get_object_or_404(EcoProject, slug=slug, is_active=True)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST

    fio        = str(data.get("fio", "")).strip()
    phone      = str(data.get("phone", "")).strip()
    address    = str(data.get("address", "")).strip()
    comment    = str(data.get("comment", "")).strip()
    service_id = data.get("service_id")
    svc_name   = str(data.get("service_name", "")).strip()

    if not fio or not address:
        return JsonResponse({"ok": False, "error": "ФИО и адрес обязательны."}, status=400)

    service = None
    if service_id:
        try:
            service  = EcoService.objects.get(id=service_id, project=project)
            svc_name = svc_name or service.name
        except EcoService.DoesNotExist:
            pass

    app = EcoApplication.objects.create(
        project=project,
        service=service,
        service_name=svc_name,
        fio=fio,
        phone=phone,
        address=address,
        comment=comment,
    )

    _notify_new_application(app)

    return JsonResponse({"ok": True})
