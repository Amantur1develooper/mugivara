"""
Dashboard views for the tech card (recipe) and ingredient warehouse module.
"""
import json
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count, Q, F

from core.models import Branch, Restaurant
from catalog.models import Item, BranchItem
from orders.models import Order, OrderItem
from techcards.models import (
    Ingredient, IngredientStock, TechCard, TechCardIngredient,
    TechCardStep, TechCardVersion, StockMovement,
)

login_url = "dashboard:login"


def _branch_or_403(request, branch_id):
    branch = get_object_or_404(Branch, pk=branch_id)
    user = request.user
    if user.is_superuser:
        return branch
    restaurant = branch.restaurant
    if restaurant.membership_set.filter(user=user).exists():
        return branch
    from django.core.exceptions import PermissionDenied
    raise PermissionDenied


def _save_version(tc, user):
    last = tc.versions.first()
    version_num = (last.version_number + 1) if last else 1
    snapshot = {
        "yield_qty": str(tc.yield_qty),
        "cooking_time": tc.cooking_time,
        "notes": tc.notes,
        "ingredients": [
            {
                "name": line.display_name(),
                "gross_qty": str(line.gross_qty),
                "waste_pct": str(line.waste_pct),
                "unit": line.unit,
            }
            for line in tc.ingredients.all()
        ],
        "steps": [s.description for s in tc.steps.all()],
    }
    TechCardVersion.objects.create(
        tech_card=tc,
        version_number=version_num,
        snapshot=snapshot,
        changed_by=user,
    )


# ── INGREDIENTS ───────────────────────────────────────────────────────────────

@login_required(login_url=login_url)
def tc_ingredient_list(request, branch_id):
    branch = _branch_or_403(request, branch_id)
    restaurant = branch.restaurant

    q = request.GET.get("q", "").strip()
    ings = Ingredient.objects.filter(restaurant=restaurant, is_active=True)
    if q:
        ings = ings.filter(name_ru__icontains=q)

    # Attach stock info for this branch
    stocks = {
        s.ingredient_id: s
        for s in IngredientStock.objects.filter(branch=branch, ingredient__in=ings)
    }
    rows = []
    for ing in ings:
        stock = stocks.get(ing.id)
        rows.append({
            "ing": ing,
            "stock": stock,
            "qty": stock.qty if stock else Decimal("0"),
            "cost": stock.cost_per_unit if stock else Decimal("0"),
        })

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_ingredient":
            name = request.POST.get("name_ru", "").strip()
            unit = request.POST.get("unit", "gr")
            if name:
                ing = Ingredient.objects.create(restaurant=restaurant, name_ru=name, unit=unit)
                # Create stock entry
                IngredientStock.objects.get_or_create(
                    branch=branch, ingredient=ing,
                    defaults={"qty": Decimal("0"), "cost_per_unit": Decimal("0")}
                )
            return redirect("dashboard:tc_ingredients", branch_id=branch_id)

        if action == "update_stock":
            ing_id = request.POST.get("ingredient_id")
            qty_str = request.POST.get("qty", "0")
            cost_str = request.POST.get("cost", "0")
            try:
                qty  = Decimal(qty_str)
                cost = Decimal(cost_str)
            except InvalidOperation:
                return redirect("dashboard:tc_ingredients", branch_id=branch_id)

            ing = get_object_or_404(Ingredient, pk=ing_id, restaurant=restaurant)
            stock, _ = IngredientStock.objects.get_or_create(
                branch=branch, ingredient=ing,
                defaults={"qty": Decimal("0"), "cost_per_unit": Decimal("0")}
            )
            old_qty = stock.qty
            diff = qty - old_qty
            stock.qty = qty
            stock.cost_per_unit = cost
            stock.save()

            if diff != 0:
                StockMovement.objects.create(
                    branch=branch, ingredient=ing,
                    qty=diff,
                    move_type=StockMovement.TYPE_MANUAL_ADD if diff > 0 else StockMovement.TYPE_MANUAL_SUB,
                    cost_per_unit=cost,
                    created_by=request.user,
                    note="Инвентаризация",
                )
            return redirect("dashboard:tc_ingredients", branch_id=branch_id)

        if action == "record_purchase":
            ing_id  = request.POST.get("ingredient_id")
            qty_str  = request.POST.get("qty", "0")
            cost_str = request.POST.get("cost", "0")
            note     = request.POST.get("note", "")
            try:
                qty  = Decimal(qty_str)
                cost = Decimal(cost_str)
            except InvalidOperation:
                return redirect("dashboard:tc_ingredients", branch_id=branch_id)

            ing = get_object_or_404(Ingredient, pk=ing_id, restaurant=restaurant)
            stock, _ = IngredientStock.objects.get_or_create(
                branch=branch, ingredient=ing,
                defaults={"qty": Decimal("0"), "cost_per_unit": Decimal("0")}
            )
            stock.qty += qty
            stock.cost_per_unit = cost  # update to latest purchase price
            stock.save()

            StockMovement.objects.create(
                branch=branch, ingredient=ing,
                qty=qty,
                move_type=StockMovement.TYPE_PURCHASE,
                cost_per_unit=cost,
                created_by=request.user,
                note=note,
            )
            return redirect("dashboard:tc_ingredients", branch_id=branch_id)

    total_value = sum(
        (s["qty"] * s["cost"]) for s in rows if s["qty"] and s["cost"]
    )

    return render(request, "dashboard/techcards/ingredients.html", {
        "branch": branch,
        "rows": rows,
        "total_value": total_value,
        "q": q,
        "unit_choices": Ingredient.UNIT_CHOICES,
    })


@login_required(login_url=login_url)
@require_POST
def tc_ingredient_delete(request, ing_id):
    ing = get_object_or_404(Ingredient, pk=ing_id)
    _branch_or_403(request, ing.restaurant.branches.filter(
        id__in=request.POST.get("branch_id", "0")
    ).values_list("id", flat=True).first() or 0)
    ing.is_active = False
    ing.save(update_fields=["is_active"])
    return JsonResponse({"ok": True})


@login_required(login_url=login_url)
@require_POST
def tc_ingredient_edit(request, ing_id):
    ing = get_object_or_404(Ingredient, pk=ing_id)
    ing.name_ru = request.POST.get("name_ru", ing.name_ru).strip()
    ing.unit    = request.POST.get("unit", ing.unit)
    ing.save(update_fields=["name_ru", "unit"])
    return JsonResponse({"ok": True, "name": ing.name_ru, "unit": ing.unit})


# ── TECH CARDS LIST ───────────────────────────────────────────────────────────

@login_required(login_url=login_url)
def tc_list(request, branch_id):
    branch = _branch_or_403(request, branch_id)
    tech_cards = (
        TechCard.objects
        .filter(branch=branch)
        .select_related("item")
        .prefetch_related("ingredients__ingredient")
        .order_by("item__name_ru")
    )

    # Items without a tech card — for quick creation
    has_tc_item_ids = tech_cards.values_list("item_id", flat=True)
    branch_items = (
        BranchItem.objects
        .filter(branch=branch, is_available=True)
        .select_related("item")
        .exclude(item_id__in=has_tc_item_ids)
    )

    cards_with_cost = []
    for tc in tech_cards:
        bi = tc.item.branch_items.filter(branch=branch).first()
        price = bi.price if bi else Decimal("0")
        cost  = tc.cost_per_serving
        margin = tc.margin()
        cards_with_cost.append({
            "tc": tc,
            "price": price,
            "cost": cost,
            "margin": margin,
            "profit": price - cost,
        })

    return render(request, "dashboard/techcards/list.html", {
        "branch": branch,
        "cards": cards_with_cost,
        "branch_items": branch_items,
    })


# ── CREATE / EDIT TECH CARD ───────────────────────────────────────────────────

@login_required(login_url=login_url)
def tc_create(request, branch_id, item_id):
    branch = _branch_or_403(request, branch_id)
    item = get_object_or_404(Item, pk=item_id)

    existing = TechCard.objects.filter(item=item, branch=branch).first()
    if existing:
        return redirect("dashboard:tc_edit", tc_id=existing.id)

    if request.method == "POST":
        yield_qty    = request.POST.get("yield_qty", "1")
        cooking_time = request.POST.get("cooking_time", "0")
        notes        = request.POST.get("notes", "")
        try:
            yield_qty = Decimal(yield_qty)
        except InvalidOperation:
            yield_qty = Decimal("1")
        tc = TechCard.objects.create(
            item=item, branch=branch,
            yield_qty=yield_qty,
            cooking_time=int(cooking_time) if cooking_time.isdigit() else 0,
            notes=notes,
        )
        _save_version(tc, request.user)
        return redirect("dashboard:tc_edit", tc_id=tc.id)

    bi = item.branch_items.filter(branch=branch).first()
    return render(request, "dashboard/techcards/create.html", {
        "branch": branch,
        "item": item,
        "branch_item": bi,
    })


@login_required(login_url=login_url)
def tc_edit(request, tc_id):
    tc = get_object_or_404(TechCard, pk=tc_id)
    branch = _branch_or_403(request, tc.branch_id)

    if request.method == "POST":
        action = request.POST.get("action", "save_header")

        if action == "save_header":
            try:
                tc.yield_qty = Decimal(request.POST.get("yield_qty", "1"))
            except InvalidOperation:
                pass
            ct = request.POST.get("cooking_time", "0")
            tc.cooking_time = int(ct) if ct.isdigit() else 0
            tc.notes = request.POST.get("notes", "")
            tc.save(update_fields=["yield_qty", "cooking_time", "notes", "updated_at"])
            _save_version(tc, request.user)
            return redirect("dashboard:tc_edit", tc_id=tc_id)

        if action == "add_ingredient":
            ing_id   = request.POST.get("ingredient_id")
            semi_id  = request.POST.get("semi_id")
            gross_qty = request.POST.get("gross_qty", "0")
            waste_pct = request.POST.get("waste_pct", "0")
            unit      = request.POST.get("unit", "gr")
            try:
                gross_qty = Decimal(gross_qty)
                waste_pct = Decimal(waste_pct)
            except InvalidOperation:
                gross_qty = Decimal("0")
                waste_pct = Decimal("0")
            line = TechCardIngredient(
                tech_card=tc, gross_qty=gross_qty, waste_pct=waste_pct, unit=unit
            )
            if ing_id:
                line.ingredient_id = ing_id
            elif semi_id:
                line.semi_finished_id = semi_id
            line.save()
            _save_version(tc, request.user)
            return redirect("dashboard:tc_edit", tc_id=tc_id)

        if action == "add_step":
            desc = request.POST.get("description", "").strip()
            if desc:
                last = tc.steps.order_by("-step_number").first()
                num = (last.step_number + 1) if last else 1
                TechCardStep.objects.create(tech_card=tc, step_number=num, description=desc)
            return redirect("dashboard:tc_edit", tc_id=tc_id)

        return redirect("dashboard:tc_edit", tc_id=tc_id)

    # GET
    ingredients = tc.ingredients.select_related("ingredient", "semi_finished__item").all()
    steps       = tc.steps.all()
    versions    = tc.versions.all()[:10]

    # Available ingredients for this branch's restaurant
    avail_ings = Ingredient.objects.filter(
        restaurant=branch.restaurant, is_active=True
    ).order_by("name_ru")
    # Semi-finished: other tech cards in same branch
    semi_finished = TechCard.objects.filter(branch=branch, is_active=True).exclude(pk=tc_id)

    # Stock status per ingredient
    stocks = {
        s.ingredient_id: s
        for s in IngredientStock.objects.filter(
            branch=branch,
            ingredient__in=[l.ingredient_id for l in ingredients if l.ingredient_id]
        )
    }

    lines_data = []
    for line in ingredients:
        stock = stocks.get(line.ingredient_id) if line.ingredient_id else None
        lines_data.append({
            "line": line,
            "stock": stock,
            "line_cost": line.line_cost,
        })

    bi = tc.item.branch_items.filter(branch=branch).first()
    price = bi.price if bi else Decimal("0")

    return render(request, "dashboard/techcards/edit.html", {
        "tc": tc,
        "branch": branch,
        "lines": lines_data,
        "steps": steps,
        "versions": versions,
        "avail_ings": avail_ings,
        "semi_finished": semi_finished,
        "unit_choices": Ingredient.UNIT_CHOICES,
        "total_cost": tc.cost_price,
        "cost_per_serving": tc.cost_per_serving,
        "price": price,
        "margin": tc.margin(),
        "markup": tc.markup(),
        "profit": price - tc.cost_per_serving,
    })


@login_required(login_url=login_url)
@require_POST
def tc_ingredient_line_delete(request, line_id):
    line = get_object_or_404(TechCardIngredient, pk=line_id)
    _branch_or_403(request, line.tech_card.branch_id)
    tc = line.tech_card
    line.delete()
    _save_version(tc, request.user)
    return JsonResponse({"ok": True})


@login_required(login_url=login_url)
@require_POST
def tc_ingredient_line_update(request, line_id):
    line = get_object_or_404(TechCardIngredient, pk=line_id)
    _branch_or_403(request, line.tech_card.branch_id)
    try:
        line.gross_qty = Decimal(request.POST.get("gross_qty", str(line.gross_qty)))
        line.waste_pct = Decimal(request.POST.get("waste_pct", str(line.waste_pct)))
        line.unit = request.POST.get("unit", line.unit)
        line.save(update_fields=["gross_qty", "waste_pct", "unit"])
    except InvalidOperation:
        return JsonResponse({"ok": False, "error": "Invalid number"})
    return JsonResponse({
        "ok": True,
        "net_qty": str(line.net_qty),
        "line_cost": str(line.line_cost),
    })


@login_required(login_url=login_url)
@require_POST
def tc_step_delete(request, step_id):
    step = get_object_or_404(TechCardStep, pk=step_id)
    _branch_or_403(request, step.tech_card.branch_id)
    step.delete()
    return JsonResponse({"ok": True})


@login_required(login_url=login_url)
@require_POST
def tc_delete(request, tc_id):
    tc = get_object_or_404(TechCard, pk=tc_id)
    _branch_or_403(request, tc.branch_id)
    branch_id = tc.branch_id
    tc.delete()
    return redirect("dashboard:tc_list", branch_id=branch_id)


# ── MANUAL WRITE-OFF ──────────────────────────────────────────────────────────

@login_required(login_url=login_url)
def tc_writeoff(request, branch_id):
    branch = _branch_or_403(request, branch_id)
    ings = Ingredient.objects.filter(restaurant=branch.restaurant, is_active=True)
    stocks = {s.ingredient_id: s for s in IngredientStock.objects.filter(branch=branch, ingredient__in=ings)}

    if request.method == "POST":
        ing_id   = request.POST.get("ingredient_id")
        qty_str  = request.POST.get("qty", "0")
        note     = request.POST.get("note", "")
        try:
            qty = Decimal(qty_str)
        except InvalidOperation:
            qty = Decimal("0")

        ing = get_object_or_404(Ingredient, pk=ing_id, restaurant=branch.restaurant)
        stock, _ = IngredientStock.objects.get_or_create(
            branch=branch, ingredient=ing,
            defaults={"qty": Decimal("0"), "cost_per_unit": Decimal("0")}
        )
        stock.qty = max(Decimal("0"), stock.qty - qty)
        stock.save(update_fields=["qty", "updated_at"])

        StockMovement.objects.create(
            branch=branch, ingredient=ing,
            qty=-qty,
            move_type=StockMovement.TYPE_WRITEOFF,
            created_by=request.user,
            note=note,
        )
        return redirect("dashboard:tc_writeoff", branch_id=branch_id)

    rows = [{"ing": i, "stock": stocks.get(i.id)} for i in ings]
    return render(request, "dashboard/techcards/writeoff.html", {
        "branch": branch,
        "rows": rows,
    })


# ── WRITE-OFF JOURNAL ─────────────────────────────────────────────────────────

@login_required(login_url=login_url)
def tc_movement_journal(request, branch_id):
    branch = _branch_or_403(request, branch_id)

    date_str = request.GET.get("date", "")
    move_type = request.GET.get("type", "")
    ing_q = request.GET.get("q", "")

    mvs = StockMovement.objects.filter(branch=branch).select_related("ingredient", "order", "created_by")

    if date_str:
        from datetime import datetime
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            mvs = mvs.filter(created_at__date=d)
        except ValueError:
            pass
    if move_type:
        mvs = mvs.filter(move_type=move_type)
    if ing_q:
        mvs = mvs.filter(ingredient__name_ru__icontains=ing_q)

    mvs = mvs[:500]

    return render(request, "dashboard/techcards/journal.html", {
        "branch": branch,
        "movements": mvs,
        "move_type_choices": StockMovement.TYPE_CHOICES,
        "sel_date": date_str,
        "sel_type": move_type,
        "q": ing_q,
    })


# ── FOOD COST REPORT ──────────────────────────────────────────────────────────

@login_required(login_url=login_url)
def tc_report(request, branch_id):
    branch = _branch_or_403(request, branch_id)

    from datetime import datetime, timedelta
    now = timezone.now()

    date_from_str = request.GET.get("from", "")
    date_to_str   = request.GET.get("to",   "")

    if date_from_str and date_to_str:
        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
            date_to   = datetime.strptime(date_to_str,   "%Y-%m-%d").date()
        except ValueError:
            date_from = now.date()
            date_to   = now.date()
    else:
        # default: last 24 hours
        date_from = (now - timedelta(hours=24)).date()
        date_to   = now.date()

    closed_orders = Order.objects.filter(
        branch=branch,
        status=Order.Status.CLOSED,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )

    total_revenue = closed_orders.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
    total_orders  = closed_orders.count()

    # Per-dish food cost breakdown
    dish_stats = {}  # item_id -> {name, qty, revenue, cost, profit}

    for oi in OrderItem.objects.filter(order__in=closed_orders).select_related("item", "order"):
        item = oi.item
        if item.id not in dish_stats:
            bi = item.branch_items.filter(branch=branch).first()
            try:
                tc = TechCard.objects.get(item=item, branch=branch, is_active=True)
                cost_per = tc.cost_per_serving
            except TechCard.DoesNotExist:
                cost_per = Decimal("0")

            dish_stats[item.id] = {
                "name": item.name_ru,
                "qty": 0,
                "revenue": Decimal("0"),
                "cost_per": cost_per,
                "cost_total": Decimal("0"),
                "has_tc": cost_per > 0,
            }
        dish_stats[item.id]["qty"]        += oi.qty
        dish_stats[item.id]["revenue"]    += oi.line_total
        dish_stats[item.id]["cost_total"] += dish_stats[item.id]["cost_per"] * oi.qty

    dish_list = sorted(dish_stats.values(), key=lambda x: x["revenue"], reverse=True)

    # Add margin to each
    for d in dish_list:
        if d["revenue"] > 0:
            d["margin"] = ((d["revenue"] - d["cost_total"]) / d["revenue"] * 100).quantize(Decimal("0.1"))
        else:
            d["margin"] = Decimal("0")
        d["profit"] = d["revenue"] - d["cost_total"]

    total_cost   = sum(d["cost_total"] for d in dish_list)
    total_profit = total_revenue - total_cost
    avg_margin   = (total_profit / total_revenue * 100).quantize(Decimal("0.1")) if total_revenue > 0 else Decimal("0")

    # Daily breakdown
    from django.db.models.functions import TruncDate
    daily_raw = (
        closed_orders
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(cnt=Count("id"), rev=Sum("total_amount"))
        .order_by("day")
    )

    # Write-offs in period
    writeoffs = StockMovement.objects.filter(
        branch=branch,
        move_type__in=[StockMovement.TYPE_WRITEOFF, StockMovement.TYPE_SALE],
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    ).select_related("ingredient")

    writeoff_cost = Decimal("0")
    for mv in writeoffs:
        if mv.cost_per_unit:
            writeoff_cost += abs(mv.qty) * mv.cost_per_unit

    # Stock current value
    stock_value = IngredientStock.objects.filter(branch=branch).aggregate(
        v=Sum(F("qty") * F("cost_per_unit"))
    )["v"] or Decimal("0")

    return render(request, "dashboard/techcards/report.html", {
        "branch": branch,
        "date_from": date_from,
        "date_to":   date_to,
        "total_revenue": total_revenue,
        "total_orders":  total_orders,
        "total_cost":    total_cost,
        "total_profit":  total_profit,
        "avg_margin":    avg_margin,
        "dish_list":     dish_list,
        "daily":         list(daily_raw),
        "writeoff_cost": writeoff_cost,
        "stock_value":   stock_value,
    })
