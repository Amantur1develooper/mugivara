from django.shortcuts import render, get_object_or_404
from .models import LegalOrg


def legal_list(request):
    orgs = LegalOrg.objects.filter(is_active=True).prefetch_related("services")
    return render(request, "legal/legal_list.html", {"orgs": orgs})


def legal_detail(request, slug):
    org = get_object_or_404(LegalOrg, slug=slug, is_active=True)
    services = org.services.filter(is_active=True)
    return render(request, "legal/legal_detail.html", {"org": org, "services": services})
