# -*- coding: utf-8 -*-
import json

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import MetalCategory, MetalCompany, MetalLead, MetalProduct


def company_list(request):
    companies = (
        MetalCompany.objects.filter(is_active=True)
        .annotate(n_products=Count("products", filter=Q(products__is_active=True)))
        .order_by("sort_order", "name")
    )
    return render(request, "metalwork/company_list.html", {"companies": companies})


def company_detail(request, slug):
    company = get_object_or_404(MetalCompany, slug=slug, is_active=True)

    q      = (request.GET.get("q") or "").strip()
    cat_id = (request.GET.get("cat") or "").strip()

    products = (
        MetalProduct.objects.filter(company=company, is_active=True)
        .select_related("category").prefetch_related("photos")
        .order_by("category__sort_order", "category_id", "sort_order", "id")
    )
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(name_ky__icontains=q) | Q(name_en__icontains=q)
            | Q(description__icontains=q) | Q(specs__icontains=q)
        )
    if cat_id.isdigit():
        products = products.filter(category_id=int(cat_id))

    categories = list(
        MetalCategory.objects.filter(company=company, is_active=True)
        .annotate(n=Count("products", filter=Q(products__is_active=True)))
        .filter(n__gt=0)
    )

    # Группируем по разделам, чтобы каталог читался сверху вниз, как в буклете.
    # При поиске или выбранном разделе группы схлопываются в один список:
    # заголовки пустых разделов там только мешают.
    grouped = []
    if not q and not cat_id:
        by_cat = {}
        for p in products:
            by_cat.setdefault(p.category_id, []).append(p)
        for c in categories:
            rows = by_cat.get(c.id, [])
            if rows:
                grouped.append({"category": c, "products": rows})
        orphans = by_cat.get(None, [])
        if orphans:
            grouped.append({"category": None, "products": orphans})

    return render(request, "metalwork/company_detail.html", {
        "company": company,
        "categories": categories,
        "products": list(products),
        "grouped": grouped,
        "q": q,
        "cat_id": cat_id,
        "total": len(products),
    })


def product_detail(request, slug, product_id):
    company = get_object_or_404(MetalCompany, slug=slug, is_active=True)
    product = get_object_or_404(
        MetalProduct.objects.select_related("category", "company").prefetch_related("photos"),
        id=product_id, company=company, is_active=True,
    )
    similar = (
        MetalProduct.objects.filter(company=company, is_active=True, category=product.category)
        .exclude(id=product.id).prefetch_related("photos")[:6]
    )
    return render(request, "metalwork/product_detail.html", {
        "company": company,
        "product": product,
        "similar": similar,
        "gallery_json": json.dumps(product.gallery),
    })


@require_POST
def lead_create(request, slug, product_id=None):
    company = get_object_or_404(MetalCompany, slug=slug, is_active=True)
    product = None
    if product_id:
        product = get_object_or_404(MetalProduct, id=product_id, company=company)

    phone = (request.POST.get("phone") or "").strip()
    if not phone:
        messages.error(request, "Укажите номер телефона — без него мы не сможем перезвонить")
    else:
        MetalLead.objects.create(
            company=company, product=product,
            name=(request.POST.get("name") or "").strip()[:120],
            phone=phone[:50],
            message=(request.POST.get("message") or "").strip(),
            source=MetalLead.Source.PRODUCT if product else MetalLead.Source.COMPANY,
        )
        messages.success(request, "Заявка принята — свяжемся с вами в рабочее время.")

    if product:
        return redirect("metalwork:product_detail", slug=slug, product_id=product.id)
    return redirect("metalwork:company_detail", slug=slug)
