from django.shortcuts import render, get_object_or_404
from .models import EcoProject


def eco_list(request):
    projects = EcoProject.objects.filter(is_active=True).prefetch_related("services")
    return render(request, "eco/eco_list.html", {"projects": projects})


def eco_detail(request, slug):
    project = get_object_or_404(EcoProject, slug=slug, is_active=True)
    services = project.services.filter(is_active=True)
    return render(request, "eco/eco_detail.html", {"project": project, "services": services})
