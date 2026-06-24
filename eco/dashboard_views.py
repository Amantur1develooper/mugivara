from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import EcoProject, EcoService, EcoMembership, EcoApplication


def _accessible_projects(user):
    """Проекты, к которым у пользователя есть доступ."""
    if user.is_superuser:
        return EcoProject.objects.all()
    ids = EcoMembership.objects.filter(user=user).values_list("project_id", flat=True)
    return EcoProject.objects.filter(id__in=ids)


@login_required(login_url="dashboard:login")
def eco_home(request):
    projects = _accessible_projects(request.user)
    return render(request, "dashboard/eco_home.html", {"projects": projects})


@login_required(login_url="dashboard:login")
def eco_applications(request, project_id):
    project = get_object_or_404(EcoProject, id=project_id)

    if not request.user.is_superuser:
        if not EcoMembership.objects.filter(user=request.user, project=project).exists():
            messages.error(request, "Нет доступа к этому проекту.")
            return redirect("dashboard:eco_home")

    status_filter = request.GET.get("status", "")
    qs = EcoApplication.objects.filter(project=project).select_related("service")
    if status_filter:
        qs = qs.filter(status=status_filter)

    return render(request, "dashboard/eco_applications.html", {
        "project":       project,
        "applications":  qs,
        "status_filter": status_filter,
        "statuses":      EcoApplication.Status.choices,
        "counts": {
            "all":       EcoApplication.objects.filter(project=project).count(),
            "new":       EcoApplication.objects.filter(project=project, status="new").count(),
            "in_work":   EcoApplication.objects.filter(project=project, status="in_work").count(),
            "done":      EcoApplication.objects.filter(project=project, status="done").count(),
            "cancelled": EcoApplication.objects.filter(project=project, status="cancelled").count(),
        },
    })


@require_POST
@login_required(login_url="dashboard:login")
def eco_application_status(request, app_id):
    """Изменить статус заявки."""
    app = get_object_or_404(EcoApplication, id=app_id)

    if not request.user.is_superuser:
        if not EcoMembership.objects.filter(user=request.user, project=app.project).exists():
            messages.error(request, "Нет доступа.")
            return redirect("dashboard:eco_home")

    new_status = request.POST.get("status", "")
    valid = [s for s, _ in EcoApplication.Status.choices]
    if new_status in valid:
        app.status = new_status
        app.save(update_fields=["status"])

    return redirect("dashboard:eco_applications", project_id=app.project_id)


def _check_access(user, project):
    """True если у пользователя есть доступ к проекту."""
    return user.is_superuser or EcoMembership.objects.filter(user=user, project=project).exists()


@login_required(login_url="dashboard:login")
def eco_services(request, project_id):
    project = get_object_or_404(EcoProject, id=project_id)
    if not _check_access(request.user, project):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:eco_home")

    services = project.services.order_by("sort_order", "id")
    return render(request, "dashboard/eco_services.html", {
        "project":  project,
        "services": services,
    })


@require_POST
@login_required(login_url="dashboard:login")
def eco_service_add(request, project_id):
    project = get_object_or_404(EcoProject, id=project_id)
    if not _check_access(request.user, project):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:eco_home")

    name       = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    price      = request.POST.get("price", "0").strip() or "0"
    price_note = request.POST.get("price_note", "").strip()

    if not name:
        messages.error(request, "Введите название услуги.")
        return redirect("dashboard:eco_services", project_id=project_id)

    try:
        price = float(price)
    except ValueError:
        price = 0

    max_order = project.services.order_by("-sort_order").values_list("sort_order", flat=True).first() or 0
    EcoService.objects.create(
        project=project,
        name=name,
        description=description,
        price=price,
        price_note=price_note,
        sort_order=max_order + 1,
    )
    messages.success(request, f"Услуга «{name}» добавлена.")
    return redirect("dashboard:eco_services", project_id=project_id)


@require_POST
@login_required(login_url="dashboard:login")
def eco_service_edit(request, service_id):
    service = get_object_or_404(EcoService, id=service_id)
    if not _check_access(request.user, service.project):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:eco_home")

    name        = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    price       = request.POST.get("price", "0").strip() or "0"
    price_note  = request.POST.get("price_note", "").strip()

    if not name:
        messages.error(request, "Название не может быть пустым.")
        return redirect("dashboard:eco_services", project_id=service.project_id)

    try:
        price = float(price)
    except ValueError:
        price = 0

    service.name        = name
    service.description = description
    service.price       = price
    service.price_note  = price_note
    service.save(update_fields=["name", "description", "price", "price_note"])
    messages.success(request, "Услуга обновлена.")
    return redirect("dashboard:eco_services", project_id=service.project_id)


@require_POST
@login_required(login_url="dashboard:login")
def eco_service_toggle(request, service_id):
    service = get_object_or_404(EcoService, id=service_id)
    if not _check_access(request.user, service.project):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:eco_home")

    service.is_active = not service.is_active
    service.save(update_fields=["is_active"])
    return redirect("dashboard:eco_services", project_id=service.project_id)


@require_POST
@login_required(login_url="dashboard:login")
def eco_service_delete(request, service_id):
    service = get_object_or_404(EcoService, id=service_id)
    if not _check_access(request.user, service.project):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:eco_home")

    project_id = service.project_id
    service.delete()
    messages.success(request, "Услуга удалена.")
    return redirect("dashboard:eco_services", project_id=project_id)
