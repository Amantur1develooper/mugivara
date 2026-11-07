# -*- coding: utf-8 -*-
"""Кабинет производства: каталог, заявки, настройки."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    MetalCategory, MetalCompany, MetalLead, MetalMembership,
    MetalProduct, MetalProductPhoto,
)

LOGIN_URL = "mcabinet:login"
MAX_PHOTOS = 10


def _decimal(raw):
    """Decimal или None. Никогда не падает: в поле цены с телефона легко
    прилетает текст, а 500 на вводе цены — худший способ об этом сообщить."""
    raw = (raw or "").strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _int(raw, default=0):
    try:
        return int((raw or "").strip())
    except (TypeError, ValueError):
        return default


def _user_companies(user):
    if user.is_staff or user.is_superuser:
        return MetalCompany.objects.all()
    ids = MetalMembership.objects.filter(user=user).values_list("company_id", flat=True)
    return MetalCompany.objects.filter(id__in=ids)


def _is_director(user, company):
    if user.is_staff or user.is_superuser:
        return True
    m = MetalMembership.objects.filter(user=user, company=company).first()
    return bool(m and m.role == MetalMembership.Role.DIRECTOR)


def _check(user, company):
    if user.is_staff or user.is_superuser:
        return True
    return MetalMembership.objects.filter(user=user, company=company).exists()


def _current(request):
    companies = _user_companies(request.user)
    cid = request.session.get("mw_company_id")
    company = companies.filter(id=cid).first() if cid else None
    if company is None:
        company = companies.first()
        if company:
            request.session["mw_company_id"] = company.id
    return company, companies


def _ctx(request, company, companies, **extra):
    ctx = {
        "company": company,
        "companies": companies,
        "is_director": _is_director(request.user, company) if company else False,
        "new_leads": MetalLead.objects.filter(company=company, status=MetalLead.Status.NEW).count()
                     if company else 0,
    }
    ctx.update(extra)
    return ctx


# ── авторизация ─────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated and _user_companies(request.user).exists():
        return redirect("mcabinet:home")
    if request.method == "POST":
        user = authenticate(request,
                            username=(request.POST.get("username") or "").strip(),
                            password=request.POST.get("password") or "")
        if user:
            login(request, user)
            return redirect("mcabinet:home")
        messages.error(request, "Неверный логин или пароль")
    return render(request, "mcabinet/login.html")


def logout_view(request):
    logout(request)
    return redirect("mcabinet:login")


@require_POST
@login_required(login_url=LOGIN_URL)
def switch_company(request, company_id):
    company = get_object_or_404(_user_companies(request.user), id=company_id)
    request.session["mw_company_id"] = company.id
    return redirect("mcabinet:home")


# ── каталог ─────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def home(request):
    company, companies = _current(request)
    if not company:
        return render(request, "mcabinet/home.html", _ctx(request, None, companies))

    products = (MetalProduct.objects.filter(company=company)
                .select_related("category").prefetch_related("photos")
                .order_by("category__sort_order", "category_id", "sort_order", "id"))
    cat_id = (request.GET.get("cat") or "").strip()
    q      = (request.GET.get("q") or "").strip()
    if cat_id.isdigit():
        products = products.filter(category_id=int(cat_id))
    if q:
        products = products.filter(Q(name__icontains=q) | Q(specs__icontains=q))

    categories = (MetalCategory.objects.filter(company=company)
                  .annotate(n=Count("products")).order_by("sort_order", "id"))
    stats = {
        "total":   MetalProduct.objects.filter(company=company).count(),
        "active":  MetalProduct.objects.filter(company=company, is_active=True).count(),
        "no_photo": MetalProduct.objects.filter(company=company, photo="").count(),
        "leads":   MetalLead.objects.filter(company=company, status=MetalLead.Status.NEW).count(),
    }
    return render(request, "mcabinet/home.html", _ctx(
        request, company, companies,
        products=list(products), categories=list(categories),
        cat_id=cat_id, q=q, stats=stats))


@login_required(login_url=LOGIN_URL)
def product_form(request, product_id=None):
    company, companies = _current(request)
    if not company:
        return redirect("mcabinet:home")

    product = None
    if product_id:
        product = get_object_or_404(MetalProduct, id=product_id)
        if not _check(request.user, product.company):
            return redirect("mcabinet:home")
        company = product.company

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Название на русском обязательно — без него изделие не найти")
        else:
            if product is None:
                product = MetalProduct(company=company)
            cat_id = (request.POST.get("category") or "").strip()
            product.category = (MetalCategory.objects.filter(company=company, id=cat_id).first()
                                if cat_id.isdigit() else None)
            product.name    = name[:200]
            product.name_ky = (request.POST.get("name_ky") or "").strip()[:200]
            product.name_en = (request.POST.get("name_en") or "").strip()[:200]
            product.description    = (request.POST.get("description") or "").strip()
            product.description_ky = (request.POST.get("description_ky") or "").strip()
            product.description_en = (request.POST.get("description_en") or "").strip()
            product.specs    = (request.POST.get("specs") or "").strip()
            product.specs_ky = (request.POST.get("specs_ky") or "").strip()
            product.specs_en = (request.POST.get("specs_en") or "").strip()
            product.price      = _decimal(request.POST.get("price"))
            product.price_from = request.POST.get("price_from") == "on"
            product.price_note    = (request.POST.get("price_note") or "").strip()[:120]
            product.price_note_ky = (request.POST.get("price_note_ky") or "").strip()[:120]
            product.price_note_en = (request.POST.get("price_note_en") or "").strip()[:120]
            product.is_custom  = request.POST.get("is_custom") == "on"
            product.is_active  = request.POST.get("is_active") == "on"
            product.sort_order = _int(request.POST.get("sort_order"))
            photo = request.FILES.get("photo")
            if photo:
                product.photo = photo
            product.save()

            for f in request.FILES.getlist("gallery")[:MAX_PHOTOS]:
                MetalProductPhoto.objects.create(product=product, photo=f)

            messages.success(request, "Изделие сохранено")
            return redirect("mcabinet:product_edit", product_id=product.id)

    categories = MetalCategory.objects.filter(company=company).order_by("sort_order", "id")
    return render(request, "mcabinet/product_form.html", _ctx(
        request, company, companies, product=product, categories=categories))


@require_POST
@login_required(login_url=LOGIN_URL)
def product_toggle(request, product_id):
    product = get_object_or_404(MetalProduct, id=product_id)
    if not _check(request.user, product.company):
        return JsonResponse({"ok": False}, status=403)
    product.is_active = not product.is_active
    product.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": product.is_active})


@require_POST
@login_required(login_url=LOGIN_URL)
def product_delete(request, product_id):
    product = get_object_or_404(MetalProduct, id=product_id)
    if not _check(request.user, product.company):
        return redirect("mcabinet:home")
    name = product.name
    product.delete()
    messages.success(request, f"Изделие «{name}» удалено")
    return redirect("mcabinet:home")


@require_POST
@login_required(login_url=LOGIN_URL)
def photo_delete(request, photo_id):
    photo = get_object_or_404(MetalProductPhoto, id=photo_id)
    if not _check(request.user, photo.product.company):
        return JsonResponse({"ok": False}, status=403)
    pid = photo.product_id
    photo.delete()
    return redirect("mcabinet:product_edit", product_id=pid)


# ── разделы ─────────────────────────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def category_add(request):
    company, _c = _current(request)
    if not company:
        return redirect("mcabinet:home")
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Введите название раздела")
    elif MetalCategory.objects.filter(company=company, name=name).exists():
        messages.error(request, f"Раздел «{name}» уже есть")
    else:
        last = MetalCategory.objects.filter(company=company).count()
        MetalCategory.objects.create(
            company=company, name=name[:200],
            name_ky=(request.POST.get("name_ky") or "").strip()[:200],
            name_en=(request.POST.get("name_en") or "").strip()[:200],
            icon=(request.POST.get("icon") or "").strip()[:8],
            sort_order=last,
        )
        messages.success(request, f"Раздел «{name}» добавлен")
    return redirect("mcabinet:categories")


@login_required(login_url=LOGIN_URL)
def categories(request):
    company, companies = _current(request)
    if not company:
        return redirect("mcabinet:home")
    if request.method == "POST":
        for cat in MetalCategory.objects.filter(company=company):
            prefix = f"cat_{cat.id}_"
            if prefix + "name" not in request.POST:
                continue
            name = (request.POST.get(prefix + "name") or "").strip()
            if name:
                cat.name = name[:200]
            cat.name_ky    = (request.POST.get(prefix + "name_ky") or "").strip()[:200]
            cat.name_en    = (request.POST.get(prefix + "name_en") or "").strip()[:200]
            cat.icon       = (request.POST.get(prefix + "icon") or "").strip()[:8]
            cat.sort_order = _int(request.POST.get(prefix + "sort"))
            cat.is_active  = request.POST.get(prefix + "active") == "on"
            cat.save()
        messages.success(request, "Разделы сохранены")
        return redirect("mcabinet:categories")

    rows = (MetalCategory.objects.filter(company=company)
            .annotate(n=Count("products")).order_by("sort_order", "id"))
    return render(request, "mcabinet/categories.html", _ctx(
        request, company, companies, rows=list(rows)))


@require_POST
@login_required(login_url=LOGIN_URL)
def category_delete(request, category_id):
    cat = get_object_or_404(MetalCategory, id=category_id)
    if not _check(request.user, cat.company):
        return redirect("mcabinet:home")
    # изделия не удаляем вместе с разделом: товар дороже группировки,
    # он просто останется без раздела и будет виден в «Остальном»
    name = cat.name
    cat.delete()
    messages.success(request, f"Раздел «{name}» удалён, изделия остались в каталоге")
    return redirect("mcabinet:categories")


# ── заявки ──────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def leads(request):
    company, companies = _current(request)
    if not company:
        return redirect("mcabinet:home")
    status = (request.GET.get("status") or "").strip()
    rows = MetalLead.objects.filter(company=company).select_related("product")
    if status in dict(MetalLead.Status.choices):
        rows = rows.filter(status=status)
    counts = {s: MetalLead.objects.filter(company=company, status=s).count()
              for s, _l in MetalLead.Status.choices}
    return render(request, "mcabinet/leads.html", _ctx(
        request, company, companies,
        rows=list(rows[:300]), status=status, counts=counts,
        statuses=MetalLead.Status.choices))


@require_POST
@login_required(login_url=LOGIN_URL)
def lead_update(request, lead_id):
    lead = get_object_or_404(MetalLead, id=lead_id)
    if not _check(request.user, lead.company):
        return redirect("mcabinet:home")
    status = (request.POST.get("status") or "").strip()
    if status in dict(MetalLead.Status.choices):
        lead.status = status
    lead.note = (request.POST.get("note") or lead.note).strip()
    lead.save(update_fields=["status", "note"])
    return redirect(request.META.get("HTTP_REFERER") or "mcabinet:leads")


# ── настройки ───────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def settings_view(request):
    company, companies = _current(request)
    if not company:
        return redirect("mcabinet:home")
    if not _is_director(request.user, company):
        messages.error(request, "Настройки меняет директор производства")
        return redirect("mcabinet:home")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Название обязательно — оставил прежнее")
        else:
            company.name = name[:200]
        for f in ("name_ky", "name_en", "tagline", "tagline_ky", "tagline_en",
                  "phone", "whatsapp", "email", "instagram", "city", "address",
                  "work_hours", "map_url"):
            if f in request.POST:
                setattr(company, f, (request.POST.get(f) or "").strip())
        for f in ("description", "description_ky", "description_en"):
            if f in request.POST:
                setattr(company, f, (request.POST.get(f) or "").strip())
        if request.FILES.get("logo"):
            company.logo = request.FILES["logo"]
        if request.FILES.get("cover"):
            company.cover = request.FILES["cover"]
        company.save()
        messages.success(request, "Настройки сохранены")
        return redirect("mcabinet:settings")

    return render(request, "mcabinet/settings.html", _ctx(request, company, companies))
