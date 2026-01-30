from collections import defaultdict
from django.db import transaction
from django.db.models import Max
"""
    Синхронизирует меню в филиал.
    Что делает:
    - если у филиала нет активных BranchMenuSet, может подключить все активные MenuSet ресторана
    - создаёт BranchCategory для всех категорий MenuSet
    - создаёт BranchItem для всех блюд, которые есть в ItemCategory
    - создаёт BranchCategoryItem для всех связей блюдо–категория
    ВАЖНО:
    - цену НЕ трогает, если BranchItem уже существует
    - is_available НЕ трогает, если BranchItem уже существует
    - sort_order проставляет только для новых записей (чтобы не ломать ручную сортировку)
    """
from collections import defaultdict
from django.db import transaction
from django.db.models import Max

from .models import (
    MenuSet, Category, Item, ItemCategory,
    BranchMenuSet, BranchCategory, BranchItem, BranchCategoryItem
)

@transaction.atomic
def sync_branch_menu(branch, *, attach_all_if_none=True):
    """
    1) Берём активные MenuSet, подключённые к филиалу (BranchMenuSet.is_active=True).
       Если их нет и attach_all_if_none=True — подключаем все активные MenuSet ресторана.
    2) Создаём BranchCategory для всех Category выбранных MenuSet
    3) Создаём BranchItem для всех Item, которые встречаются в ItemCategory этих категорий
       (цена по умолчанию = Item.base_price, но существующие цены НЕ трогаем)
    4) Создаём BranchCategoryItem для всех связей блюдо-категория, сорт = ItemCategory.sort_order
    """

    # ---- MenuSet для филиала
    bms = BranchMenuSet.objects.select_related("menu_set").filter(
        branch=branch, is_active=True, menu_set__is_active=True
    )

    if not bms.exists() and attach_all_if_none:
        menu_sets = MenuSet.objects.filter(restaurant=branch.restaurant, is_active=True)
        BranchMenuSet.objects.bulk_create(
            [BranchMenuSet(branch=branch, menu_set=ms, is_active=True) for ms in menu_sets],
            ignore_conflicts=True
        )
        bms = BranchMenuSet.objects.select_related("menu_set").filter(
            branch=branch, is_active=True, menu_set__is_active=True
        )

    menu_set_ids = list(bms.values_list("menu_set_id", flat=True))
    if not menu_set_ids:
        return {"menu_sets": 0, "branch_categories": 0, "branch_items": 0, "links": 0}

    # ---- Категории этих MenuSet
    categories = list(Category.objects.filter(menu_set_id__in=menu_set_ids).order_by("id"))
    category_ids = [c.id for c in categories]
    if not category_ids:
        return {"menu_sets": len(menu_set_ids), "branch_categories": 0, "branch_items": 0, "links": 0}

    # ---- BranchCategory (создаём недостающие)
    existing_cat_ids = set(
        BranchCategory.objects.filter(branch=branch, category_id__in=category_ids)
        .values_list("category_id", flat=True)
    )
    missing_cats = [c for c in categories if c.id not in existing_cat_ids]

    created_bc = 0
    if missing_cats:
        max_sort = BranchCategory.objects.filter(branch=branch).aggregate(m=Max("sort_order"))["m"] or 0
        objs = []
        for i, c in enumerate(missing_cats, start=1):
            objs.append(BranchCategory(
                branch=branch,
                category=c,
                is_active=True,
                sort_order=max_sort + i
            ))
        BranchCategory.objects.bulk_create(objs, ignore_conflicts=True)
        created_bc = len(objs)

    # mapping category_id -> branch_category_id
    bc_map = dict(
        BranchCategory.objects.filter(branch=branch, category_id__in=category_ids)
        .values_list("category_id", "id")
    )

    # ---- ItemCategory для этих категорий
    ic_rows = list(
        ItemCategory.objects.select_related("item", "category")
        .filter(category_id__in=category_ids)
        .order_by("category_id", "sort_order", "id")
    )
    item_ids = sorted(set(r.item_id for r in ic_rows))
    if not item_ids:
        return {"menu_sets": len(menu_set_ids), "branch_categories": created_bc, "branch_items": 0, "links": 0}

    # ---- BranchItem (создаём недостающие)
    existing_item_ids = set(
        BranchItem.objects.filter(branch=branch, item_id__in=item_ids)
        .values_list("item_id", flat=True)
    )
    items = list(Item.objects.filter(id__in=item_ids).order_by("id"))

    # базовый sort для нового блюда — минимальный sort_order из ItemCategory
    min_sort_for_item = defaultdict(lambda: 0)
    for r in ic_rows:
        if r.item_id not in min_sort_for_item:
            min_sort_for_item[r.item_id] = r.sort_order

    missing_items = [it for it in items if it.id not in existing_item_ids]
    created_bi = 0
    if missing_items:
        objs = []
        for it in missing_items:
            objs.append(BranchItem(
                branch=branch,
                item=it,
                price=it.base_price,       # только при создании
                is_available=True,
                sort_order=min_sort_for_item.get(it.id, 0)
            ))
        BranchItem.objects.bulk_create(objs, ignore_conflicts=True)
        created_bi = len(objs)

    # mapping item_id -> branch_item_id
    bi_map = dict(
        BranchItem.objects.filter(branch=branch, item_id__in=item_ids)
        .values_list("item_id", "id")
    )

    # ---- BranchCategoryItem (создаём недостающие связи)
    pairs = []
    for r in ic_rows:
        bc_id = bc_map.get(r.category_id)
        bi_id = bi_map.get(r.item_id)
        if bc_id and bi_id:
            pairs.append((bc_id, bi_id, r.sort_order))

    existing_pairs = set(
        BranchCategoryItem.objects.filter(
            branch_category_id__in=[p[0] for p in pairs],
            branch_item_id__in=[p[1] for p in pairs],
        ).values_list("branch_category_id", "branch_item_id")
    )

    new_links = []
    for bc_id, bi_id, sort_order in pairs:
        if (bc_id, bi_id) in existing_pairs:
            continue
        new_links.append(BranchCategoryItem(
            branch_category_id=bc_id,
            branch_item_id=bi_id,
            sort_order=sort_order
        ))

    BranchCategoryItem.objects.bulk_create(new_links, ignore_conflicts=True)

    return {
        "menu_sets": len(menu_set_ids),
        "branch_categories": created_bc,
        "branch_items": created_bi,
        "links": len(new_links),
    }
from django.db.models import Max

def ensure_links_for_branch_item(branch_item):
    """
    Когда вручную добавили BranchItem в филиал —
    автоматически:
    - создаём BranchCategory (если нет)
    - создаём BranchCategoryItem (если нет)
    Берём категории из ItemCategory (и сортировку тоже).
    Учитываем только активные MenuSet, подключённые к филиалу.
    """
    branch = branch_item.branch

    menu_set_ids = list(
        BranchMenuSet.objects.filter(
            branch=branch, is_active=True, menu_set__is_active=True
        ).values_list("menu_set_id", flat=True)
    )
    if not menu_set_ids:
        return {"branch_categories": 0, "links": 0}

    ic_rows = list(
        ItemCategory.objects.select_related("category")
        .filter(item=branch_item.item, category__menu_set_id__in=menu_set_ids)
        .order_by("sort_order", "id")
    )
    if not ic_rows:
        return {"branch_categories": 0, "links": 0}

    category_ids = [r.category_id for r in ic_rows]

    # BranchCategory (создать недостающие)
    existing_cat_ids = set(
        BranchCategory.objects.filter(branch=branch, category_id__in=category_ids)
        .values_list("category_id", flat=True)
    )
    missing_cats = [r.category for r in ic_rows if r.category_id not in existing_cat_ids]

    created_bc = 0
    if missing_cats:
        max_sort = BranchCategory.objects.filter(branch=branch).aggregate(m=Max("sort_order"))["m"] or 0
        objs = []
        for i, cat in enumerate(missing_cats, start=1):
            objs.append(BranchCategory(
                branch=branch,
                category=cat,
                is_active=True,
                sort_order=max_sort + i
            ))
        BranchCategory.objects.bulk_create(objs, ignore_conflicts=True)
        created_bc = len(objs)

    bc_map = dict(
        BranchCategory.objects.filter(branch=branch, category_id__in=category_ids)
        .values_list("category_id", "id")
    )

    # BranchCategoryItem (создать недостающие связи)
    existing_pairs = set(
        BranchCategoryItem.objects.filter(
            branch_item=branch_item,
            branch_category_id__in=list(bc_map.values())
        ).values_list("branch_category_id", "branch_item_id")
    )

    new_links = []
    for r in ic_rows:
        bc_id = bc_map.get(r.category_id)
        if not bc_id:
            continue
        if (bc_id, branch_item.id) in existing_pairs:
            continue
        new_links.append(BranchCategoryItem(
            branch_category_id=bc_id,
            branch_item=branch_item,
            sort_order=r.sort_order
        ))

    BranchCategoryItem.objects.bulk_create(new_links, ignore_conflicts=True)

    return {"branch_categories": created_bc, "links": len(new_links)}
