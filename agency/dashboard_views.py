from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages

from .models import Agency, AgencyService, AgencyMembership

LOGIN_URL = "dashboard:login"


def _user_agencies(user):
    if user.is_staff or user.is_superuser:
        return Agency.objects.all()
    ids = AgencyMembership.objects.filter(user=user).values_list("agency_id", flat=True)
    return Agency.objects.filter(id__in=ids)


def _check_access(user, agency):
    if user.is_staff or user.is_superuser:
        return True
    return AgencyMembership.objects.filter(user=user, agency=agency).exists()


@login_required(login_url=LOGIN_URL)
def agency_home(request):
    agencies = _user_agencies(request.user).prefetch_related("services")
    return render(request, "dashboard/agency/home.html", {"agencies": agencies})


@login_required(login_url=LOGIN_URL)
def agency_edit(request, agency_id):
    agency = get_object_or_404(Agency, id=agency_id)
    if not _check_access(request.user, agency):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:agency_home")

    if request.method == "POST":
        agency.name        = request.POST.get("name", agency.name).strip()
        agency.tagline     = request.POST.get("tagline", "").strip()
        agency.description = request.POST.get("description", "").strip()
        agency.website     = request.POST.get("website", "").strip()
        agency.phone       = request.POST.get("phone", "").strip()
        agency.email       = request.POST.get("email", "").strip()
        agency.address     = request.POST.get("address", "").strip()
        agency.tg_chat_id  = request.POST.get("tg_chat_id", "").strip()
        tg_thread = request.POST.get("tg_thread_id", "").strip()
        agency.tg_thread_id = int(tg_thread) if tg_thread.isdigit() else None

        if "logo" in request.FILES:
            agency.logo = request.FILES["logo"]
        elif request.POST.get("logo_clear"):
            agency.logo = None

        if "cover" in request.FILES:
            agency.cover = request.FILES["cover"]
        elif request.POST.get("cover_clear"):
            agency.cover = None

        agency.save()
        messages.success(request, "Данные агентства обновлены.")
        return redirect("dashboard:agency_edit", agency_id=agency.id)

    return render(request, "dashboard/agency/agency_edit.html", {"agency": agency})


@login_required(login_url=LOGIN_URL)
def agency_services(request, agency_id):
    agency = get_object_or_404(Agency, id=agency_id)
    if not _check_access(request.user, agency):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:agency_home")

    services = agency.services.all()
    return render(request, "dashboard/agency/services.html", {"agency": agency, "services": services})


@login_required(login_url=LOGIN_URL)
def agency_service_add(request, agency_id):
    agency = get_object_or_404(Agency, id=agency_id)
    if not _check_access(request.user, agency):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:agency_home")

    if request.method == "POST":
        svc = AgencyService(agency=agency)
        svc.name          = request.POST.get("name", "").strip()
        svc.service_type  = request.POST.get("service_type", "dev")
        svc.description   = request.POST.get("description", "").strip()
        svc.tech_stack    = request.POST.get("tech_stack", "").strip()
        svc.price         = request.POST.get("price") or 0
        svc.price_note    = request.POST.get("price_note", "").strip()
        days = request.POST.get("delivery_days", "").strip()
        svc.delivery_days = int(days) if days.isdigit() else None
        svc.sort_order    = request.POST.get("sort_order") or 0
        if "photo" in request.FILES:
            svc.photo = request.FILES["photo"]
        if not svc.name:
            messages.error(request, "Введите название услуги.")
        else:
            svc.save()
            messages.success(request, f"Услуга «{svc.name}» добавлена.")
            return redirect("dashboard:agency_services", agency_id=agency.id)

    from .models import SERVICE_TYPE_CHOICES
    return render(request, "dashboard/agency/service_form.html",
                  {"agency": agency, "svc": None, "service_types": SERVICE_TYPE_CHOICES})


@login_required(login_url=LOGIN_URL)
def agency_service_edit(request, svc_id):
    svc = get_object_or_404(AgencyService, id=svc_id)
    agency = svc.agency
    if not _check_access(request.user, agency):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:agency_home")

    if request.method == "POST":
        svc.name          = request.POST.get("name", svc.name).strip()
        svc.service_type  = request.POST.get("service_type", svc.service_type)
        svc.description   = request.POST.get("description", "").strip()
        svc.tech_stack    = request.POST.get("tech_stack", "").strip()
        svc.price         = request.POST.get("price") or 0
        svc.price_note    = request.POST.get("price_note", "").strip()
        days = request.POST.get("delivery_days", "").strip()
        svc.delivery_days = int(days) if days.isdigit() else None
        svc.sort_order    = request.POST.get("sort_order") or 0
        if "photo" in request.FILES:
            svc.photo = request.FILES["photo"]
        elif request.POST.get("photo_clear"):
            svc.photo = None
        svc.save()
        messages.success(request, f"Услуга «{svc.name}» обновлена.")
        return redirect("dashboard:agency_services", agency_id=agency.id)

    from .models import SERVICE_TYPE_CHOICES
    return render(request, "dashboard/agency/service_form.html",
                  {"agency": agency, "svc": svc, "service_types": SERVICE_TYPE_CHOICES})


@require_POST
@login_required(login_url=LOGIN_URL)
def agency_service_toggle(request, svc_id):
    svc = get_object_or_404(AgencyService, id=svc_id)
    if not _check_access(request.user, svc.agency):
        return JsonResponse({"ok": False}, status=403)
    svc.is_active = not svc.is_active
    svc.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": svc.is_active})


@require_POST
@login_required(login_url=LOGIN_URL)
def agency_service_delete(request, svc_id):
    svc = get_object_or_404(AgencyService, id=svc_id)
    agency_id = svc.agency_id
    if not _check_access(request.user, svc.agency):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:agency_home")
    svc.delete()
    messages.success(request, "Услуга удалена.")
    return redirect("dashboard:agency_services", agency_id=agency_id)
