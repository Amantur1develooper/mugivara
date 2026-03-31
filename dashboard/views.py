from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from decimal import Decimal, InvalidOperation

from core.models import Restaurant, Branch, Membership
from catalog.models import (
    BranchItem, BranchCategory, BranchCategoryItem,
    Item, ItemCategory, Category,
)
from catalog.services import ensure_links_for_branch_item


def _user_restaurants(user):
    ids = Membership.objects.filter(user=user).values_list("restaurant_id", flat=True)
    return Restaurant.objects.filter(id__in=ids)


def _has_branch_access(user, branch):
    return Membership.objects.filter(user=user, restaurant=branch.restaurant).exists()


# ── AUTH ─────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user:
            login(request, user)
            return redirect("dashboard:home")
        messages.error(request, "Неверный логин или пароль")

    return render(request, "dashboard/login.html")


def logout_view(request):
    logout(request)
    return redirect("dashboard:login")


# ── HOME ─────────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def home(request):
    restaurants = _user_restaurants(request.user).prefetch_related("branches")
    data = []
    for r in restaurants:
        branches = list(r.branches.filter(is_active=True).order_by("name_ru"))
        data.append({"restaurant": r, "branches": branches})
    return render(request, "dashboard/home.html", {"data": data})


# ── RESTAURANT ───────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def restaurant_edit(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    if not Membership.objects.filter(user=request.user, restaurant=restaurant).exists():
        return redirect("dashboard:home")

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            restaurant.name_ru = name
        restaurant.about_ru = request.POST.get("about_ru", "").strip()
        restaurant.save(update_fields=["name_ru", "about_ru", "updated_at"])
        messages.success(request, "Данные ресторана сохранены")
        return redirect("dashboard:restaurant_edit", restaurant_id=restaurant.id)

    return render(request, "dashboard/restaurant_edit.html", {"restaurant": restaurant})


# ── BRANCH SETTINGS ──────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def branch_edit(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    if request.method == "POST":
        def dec(key, default="0"):
            try:
                return Decimal(request.POST.get(key) or default)
            except InvalidOperation:
                return Decimal(default)

        branch.delivery_enabled   = request.POST.get("delivery_enabled") == "on"
        branch.min_order_amount   = dec("min_order_amount")
        branch.delivery_fee       = dec("delivery_fee")
        branch.free_delivery_from = dec("free_delivery_from")
        branch.is_open_24h        = request.POST.get("is_open_24h") == "on"

        ot = request.POST.get("open_time", "").strip()
        ct = request.POST.get("close_time", "").strip()
        branch.open_time  = ot or None
        branch.close_time = ct or None

        branch.save(update_fields=[
            "delivery_enabled", "min_order_amount", "delivery_fee",
            "free_delivery_from", "is_open_24h", "open_time", "close_time", "updated_at",
        ])
        messages.success(request, "Настройки филиала сохранены")
        return redirect("dashboard:branch_edit", branch_id=branch.id)

    return render(request, "dashboard/branch_edit.html", {"branch": branch})


# ── BRANCH MENU (prices + list) ───────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def branch_items(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .order_by("sort_order", "id")
    )

    menu = []
    for bc in categories:
        items = (
            BranchCategoryItem.objects
            .filter(branch_category=bc)
            .select_related("branch_item__item")
            .order_by("sort_order", "id")
        )
        menu.append({"category": bc, "items": list(items)})

    return render(request, "dashboard/branch_items.html", {
        "branch": branch,
        "menu": menu,
    })


# ── ADD ITEM ─────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def item_add(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:home")

    restaurant = branch.restaurant
    categories = (
        BranchCategory.objects
        .filter(branch=branch, is_active=True)
        .select_related("category")
        .order_by("sort_order", "id")
    )

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if not name:
            messages.error(request, "Укажите название блюда")
            return redirect("dashboard:item_add", branch_id=branch.id)

        try:
            price = Decimal(request.POST.get("price") or "0")
        except InvalidOperation:
            price = Decimal("0")

        description = request.POST.get("description_ru", "").strip()
        photo = request.FILES.get("photo")

        # создаём Item
        item = Item(
            restaurant=restaurant,
            name_ru=name,
            description_ru=description,
            base_price=price,
        )
        if photo:
            item.photo = photo
        item.save()

        c = item.photo_compression
        if c:
            photo_msg = (
                f" | Фото: {c['before_kb']} KB → {c['after_kb']} KB "
                f"(−{c['saved_pct']}%, {c['orig_size']} → {c['new_size']})"
            )
        else:
            photo_msg = ""

        # создаём BranchItem
        bi = BranchItem.objects.create(
            branch=branch,
            item=item,
            price=price,
            is_available=True,
        )

        # привязываем к категории если выбрана
        branch_cat_id = request.POST.get("branch_category_id")
        if branch_cat_id:
            try:
                bc = BranchCategory.objects.get(id=branch_cat_id, branch=branch)
                # создаём ItemCategory (связь Item <-> Category)
                ic, _ = ItemCategory.objects.get_or_create(
                    item=item,
                    category=bc.category,
                    defaults={"sort_order": 0},
                )
                # создаём BranchCategoryItem
                BranchCategoryItem.objects.get_or_create(
                    branch_category=bc,
                    branch_item=bi,
                    defaults={"sort_order": 0},
                )
            except BranchCategory.DoesNotExist:
                pass
        else:
            # без категории — просто пробуем автосвязи
            ensure_links_for_branch_item(bi)

        messages.success(request, f"Блюдо «{name}» добавлено{photo_msg}")
        return redirect("dashboard:branch_items", branch_id=branch.id)

    return render(request, "dashboard/item_add.html", {
        "branch": branch,
        "categories": categories,
    })


# ── EDIT ITEM ─────────────────────────────────────────────────────────────────

@login_required(login_url="dashboard:login")
def item_edit(request, branch_item_id):
    bi = get_object_or_404(BranchItem, id=branch_item_id)
    if not _has_branch_access(request.user, bi.branch):
        return redirect("dashboard:home")

    item = bi.item

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            item.name_ru = name
        item.description_ru = request.POST.get("description_ru", "").strip()

        try:
            bi.price = Decimal(request.POST.get("price") or "0")
        except InvalidOperation:
            pass
        bi.is_available = request.POST.get("is_available") == "on"

        photo = request.FILES.get("photo")
        if photo:
            item.photo = photo

        item.save()
        bi.save(update_fields=["price", "is_available", "updated_at"])

        c = item.photo_compression
        if c:
            photo_msg = (
                f" | Фото: {c['before_kb']} KB → {c['after_kb']} KB "
                f"(−{c['saved_pct']}%, {c['orig_size']} → {c['new_size']})"
            )
            messages.success(request, f"Блюдо обновлено{photo_msg}")
        else:
            messages.success(request, "Блюдо обновлено")
        return redirect("dashboard:branch_items", branch_id=bi.branch_id)

    return render(request, "dashboard/item_edit.html", {"bi": bi, "item": item})


# ── AJAX: update price ────────────────────────────────────────────────────────

@require_POST
@login_required(login_url="dashboard:login")
def update_item_price(request, branch_item_id):
    bi = get_object_or_404(BranchItem, id=branch_item_id)
    if not _has_branch_access(request.user, bi.branch):
        return JsonResponse({"ok": False}, status=403)
    try:
        price = Decimal(request.POST.get("price", ""))
        if price < 0:
            raise ValueError
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректная цена"})

    bi.price = price
    bi.save(update_fields=["price", "updated_at"])
    return JsonResponse({"ok": True, "price": str(bi.price)})


# ── AJAX: toggle availability ─────────────────────────────────────────────────

@require_POST
@login_required(login_url="dashboard:login")
def toggle_item(request, branch_item_id):
    bi = get_object_or_404(BranchItem, id=branch_item_id)
    if not _has_branch_access(request.user, bi.branch):
        return JsonResponse({"ok": False}, status=403)

    bi.is_available = not bi.is_available
    bi.save(update_fields=["is_available", "updated_at"])
    return JsonResponse({"ok": True, "is_available": bi.is_available})
