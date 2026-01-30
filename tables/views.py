from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from tables.models import Table, TableSession
from catalog.models import BranchCategory, BranchCategoryItem
from orders.models import Order, OrderItem
from catalog.models import BranchItem

@api_view(["GET"])
def table_menu(request, token: str):
    table = get_object_or_404(Table, qr_token=token)
    branch = table.branch

    categories = BranchCategory.objects.filter(branch=branch, is_active=True).order_by("sort_order", "id")
    data = []
    for bc in categories:
        items_in_cat = BranchCategoryItem.objects.select_related("branch_item__item").filter(
            branch_category=bc,
            branch_item__is_available=True,
        ).order_by("sort_order", "id")

        data.append({
            "category_id": bc.category_id,
            "category_name": bc.category.name,
            "items": [{
                "branch_item_id": x.branch_item_id,
                "item_id": x.branch_item.item_id,
                "name": x.branch_item.item.name,
                "description": x.branch_item.item.description,
                "price": str(x.branch_item.price),
                "available": x.branch_item.is_available,
            } for x in items_in_cat]
        })

    return Response({
        "branch": {"id": branch.id, "name": branch.name},
        "table": {"id": table.id, "number": table.number},
        "menu": data
    })

@api_view(["POST"])
def table_create_order(request, token: str):
    table = get_object_or_404(Table, qr_token=token)
    branch = table.branch

    # open session (простая логика)
    session, _ = TableSession.objects.get_or_create(table=table, status=TableSession.Status.OPEN)

    items = request.data.get("items", [])  # [{branch_item_id, qty}]
    if not items:
        return Response({"detail": "items пустой"}, status=status.HTTP_400_BAD_REQUEST)

    order = Order.objects.create(
        branch=branch,
        type=Order.Type.DINE_IN,
        status=Order.Status.NEW,
        table_session=session,
        comment=request.data.get("comment", "")
    )

    total = 0
    for row in items:
        bi = get_object_or_404(BranchItem, id=row["branch_item_id"], branch=branch)
        qty = int(row.get("qty", 1))
        price = bi.price
        line_total = price * qty
        total += line_total

        OrderItem.objects.create(
            order=order,
            item=bi.item,
            qty=qty,
            price_snapshot=price,
            line_total=line_total
        )

    order.total_amount = total
    order.save(update_fields=["total_amount"])

    return Response({"order_id": order.id, "total": str(order.total_amount)}, status=status.HTTP_201_CREATED)
