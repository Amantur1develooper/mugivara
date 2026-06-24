import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import EcoProject, EcoService, EcoApplication


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

    EcoApplication.objects.create(
        project=project,
        service=service,
        service_name=svc_name,
        fio=fio,
        phone=phone,
        address=address,
        comment=comment,
    )

    return JsonResponse({"ok": True})
