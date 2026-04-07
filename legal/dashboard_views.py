from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages

from .models import LegalOrg, LegalService, LegalMembership

LOGIN_URL = "dashboard:login"


def _user_orgs(user):
    if user.is_staff or user.is_superuser:
        return LegalOrg.objects.all()
    ids = LegalMembership.objects.filter(user=user).values_list("org_id", flat=True)
    return LegalOrg.objects.filter(id__in=ids)


def _check_org_access(user, org):
    if user.is_staff or user.is_superuser:
        return True
    return LegalMembership.objects.filter(user=user, org=org).exists()


# ── СПИСОК ОРГАНИЗАЦИЙ ────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def legal_home(request):
    orgs = _user_orgs(request.user).prefetch_related("services")
    return render(request, "dashboard/legal/home.html", {"orgs": orgs})


# ── РЕДАКТИРОВАНИЕ ОРГАНИЗАЦИИ ────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def legal_org_edit(request, org_id):
    org = get_object_or_404(LegalOrg, id=org_id)
    if not _check_org_access(request.user, org):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:legal_home")

    if request.method == "POST":
        org.name          = request.POST.get("name", org.name).strip()
        org.description   = request.POST.get("description", "").strip()
        org.address       = request.POST.get("address", "").strip()
        org.phone         = request.POST.get("phone", "").strip()
        org.working_hours = request.POST.get("working_hours", "").strip()
        org.map_url       = request.POST.get("map_url", "").strip()
        org.tg_chat_id    = request.POST.get("tg_chat_id", "").strip()
        tg_thread = request.POST.get("tg_thread_id", "").strip()
        org.tg_thread_id  = int(tg_thread) if tg_thread.isdigit() else None

        if "logo" in request.FILES:
            org.logo = request.FILES["logo"]
        elif request.POST.get("logo_clear"):
            org.logo = None

        org.save()
        messages.success(request, "Данные организации обновлены.")
        return redirect("dashboard:legal_org_edit", org_id=org.id)

    return render(request, "dashboard/legal/org_edit.html", {"org": org})


# ── СПИСОК УСЛУГ ──────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def legal_services(request, org_id):
    org = get_object_or_404(LegalOrg, id=org_id)
    if not _check_org_access(request.user, org):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:legal_home")

    services = org.services.all()
    return render(request, "dashboard/legal/services.html", {"org": org, "services": services})


# ── ДОБАВИТЬ УСЛУГУ ───────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def legal_service_add(request, org_id):
    org = get_object_or_404(LegalOrg, id=org_id)
    if not _check_org_access(request.user, org):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:legal_home")

    if request.method == "POST":
        svc = LegalService(org=org)
        svc.name        = request.POST.get("name", "").strip()
        svc.description = request.POST.get("description", "").strip()
        svc.price       = request.POST.get("price") or 0
        svc.price_note  = request.POST.get("price_note", "").strip()
        svc.sort_order  = request.POST.get("sort_order") or 0
        if "photo" in request.FILES:
            svc.photo = request.FILES["photo"]
        if not svc.name:
            messages.error(request, "Введите название услуги.")
        else:
            svc.save()
            messages.success(request, f"Услуга «{svc.name}» добавлена.")
            return redirect("dashboard:legal_services", org_id=org.id)

    return render(request, "dashboard/legal/service_form.html", {"org": org, "svc": None})


# ── РЕДАКТИРОВАТЬ УСЛУГУ ──────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def legal_service_edit(request, svc_id):
    svc = get_object_or_404(LegalService, id=svc_id)
    org = svc.org
    if not _check_org_access(request.user, org):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:legal_home")

    if request.method == "POST":
        svc.name        = request.POST.get("name", svc.name).strip()
        svc.description = request.POST.get("description", "").strip()
        svc.price       = request.POST.get("price") or 0
        svc.price_note  = request.POST.get("price_note", "").strip()
        svc.sort_order  = request.POST.get("sort_order") or 0
        if "photo" in request.FILES:
            svc.photo = request.FILES["photo"]
        elif request.POST.get("photo_clear"):
            svc.photo = None
        svc.save()
        messages.success(request, f"Услуга «{svc.name}» обновлена.")
        return redirect("dashboard:legal_services", org_id=org.id)

    return render(request, "dashboard/legal/service_form.html", {"org": org, "svc": svc})


# ── ПЕРЕКЛЮЧИТЬ АКТИВНОСТЬ ────────────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def legal_service_toggle(request, svc_id):
    svc = get_object_or_404(LegalService, id=svc_id)
    if not _check_org_access(request.user, svc.org):
        return JsonResponse({"ok": False}, status=403)
    svc.is_active = not svc.is_active
    svc.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": svc.is_active})


# ── УДАЛИТЬ УСЛУГУ ────────────────────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def legal_service_delete(request, svc_id):
    svc = get_object_or_404(LegalService, id=svc_id)
    org_id = svc.org_id
    if not _check_org_access(request.user, svc.org):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:legal_home")
    svc.delete()
    messages.success(request, "Услуга удалена.")
    return redirect("dashboard:legal_services", org_id=org_id)
