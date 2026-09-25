#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Добавляет 5 новых товаров в магазин "Трайфл лавка" (webordo.kg/ru/shops/b/41/).

Источник фото: photos_traifl/ (JPEG, по слагу) — вырезаны из промо-картинок
магазина (WhatsApp), без текстового оверлея, под стиль уже существующего фото
товара "МАКСИ бокс".

"МАКСИ бокс" уже существует в магазине — этот скрипт его НЕ трогает (пропускает,
если товар с таким именем уже есть под этим store). Добавляются только 5 новых:
Банкейки (4 вкуса), 8 вкусов, 6 вкусов, 4 вкуса, Банкейки (2 вкуса).

Все товары кладутся в существующую категорию "Трайфл" (создаётся, если её
почему-то нет) и получают запас (StoreStock) на филиале --branch-id.

Запуск (из корня проекта, из активного venv):
    python add_traifl_products.py --dry-run
    python add_traifl_products.py

Параметры:
    --dry-run         показать, что будет сделано, не писать в БД
    --branch-id N     ID филиала (по умолчанию 41, как в присланной ссылке)
    --stock N         начальный остаток на складе филиала для каждого нового
                       товара (по умолчанию 5)
"""
import argparse
import os
import sys
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "photos_traifl")

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.core.files.base import ContentFile
from django.db import transaction

from shops.models import Store, StoreBranch, StoreCategory, StoreProduct, StoreStock

PRODUCTS = [
    dict(
        slug="bankeyki_4", price=1500,
        name_ru="Банкейки, 4 вкуса в одной коробке",
        name_ky="Банкейки, 1 кутучада 4 даам",
        name_en="Bankeyki — 4 Flavors in One Box",
        desc_ru="Небольшой подарок с большим смыслом 🤍 4 баночных десерта, 4 разных "
                "вкуса — нежные бисквитные слои, кремы и свежие ягодные топинги в "
                "стеклянных баночках с золотой крышкой. Подарочная упаковка с лентой "
                "— готово дарить сразу из коробки.",
        desc_ky="Чоң мааниси бар кичине белек 🤍 4 банкадагы десерт, 4 ар түрдүү даам "
                "— назик бисквит катмарлары, кремдер жана таза мөмө-жемиш каптары "
                "алтын капкактуу айнек банкаларда. Тасма менен кооздолгон белек кабы "
                "— коробкадан түз эле белекке берүүгө даяр.",
        desc_en="A small gift with a big meaning 🤍 4 jar desserts, 4 different "
                "flavors — delicate sponge layers, creams and fresh fruit toppings "
                "in glass jars with a gold lid. Gift-wrapped with a ribbon — ready "
                "to give straight from the box.",
    ),
    dict(
        slug="vkusov_8", price=2000,
        name_ru="8 вкусов в одной коробке",
        name_ky="1 кутучада 8 даам",
        name_en="8 Flavors in One Box",
        desc_ru="8 вкусов трайфлов в одной эффектной коробке 🍰 Каждый кусочек — "
                "свой вкус: от карамели и фисташки до маракуйи и вишни. Мягкие "
                "бисквитные слои, нежные кремы и яркие топинги. Отличный вариант, "
                "чтобы порадовать сразу нескольких человек или устроить дегустацию "
                "дома.",
        desc_ky="Бир кооз кутучада 8 даам трайфл 🍰 Ар бир кесим өзүнчө даамга ээ: "
                "карамель менен фисташкадан баштап маракуйя жана мисмишке чейин. "
                "Жумшак бисквит катмарлары, назик крем жана жаркыраган каптар. Бир "
                "нече адамды суйундуруу же үйдө даам таттыруу уюштуруу үчүн эң "
                "ыңгайлуу.",
        desc_en="8 trayfl flavors in one eye-catching box 🍰 Every slice is a "
                "different taste — from caramel and pistachio to passion fruit and "
                "cherry. Soft sponge layers, delicate creams and vibrant toppings. "
                "Perfect for treating several people at once or hosting a tasting "
                "at home.",
    ),
    dict(
        slug="vkusov_6", price=1800,
        name_ru="6 вкусов в одной коробке",
        name_ky="1 кутучада 6 даам",
        name_en="6 Flavors in One Box",
        desc_ru="6 вкусов трайфлов в подарочной коробке с лентой 🎀 Квадратные "
                "порции с разными начинками — фисташка, маракуйя, вишня, карамель "
                "и другие. Нежные кремы и свежий бисквит в каждом кусочке.",
        desc_ky="Тасмалуу белек кутучасында 6 даам трайфл 🎀 Ар түрдүү толтурмалары "
                "бар чарчы порциялар — фисташка, маракуйя, мисмиш, карамель жана "
                "башкалар. Ар бир кесимде назик крем жана таза бисквит.",
        desc_en="6 trayfl flavors in a ribbon-tied gift box 🎀 Square portions with "
                "different fillings — pistachio, passion fruit, cherry, caramel and "
                "more. Delicate cream and fresh sponge in every bite.",
    ),
    dict(
        slug="vkusa_4", price=1200,
        name_ru="4 вкуса — идеальный небольшой подарок",
        name_ky="4 даам — идеалдуу кичине белек",
        name_en="4 Flavors — The Perfect Small Gift",
        desc_ru="Идеальный небольшой подарок 🤍 4 вкуса трайфлов в компактной "
                "коробке — фисташка, маракуйя, карамель и вишня. Красивая "
                "подарочная упаковка с лентой, готово дарить сразу.",
        desc_ky="Идеалдуу кичине белек 🤍 Компакттуу кутучада 4 даам трайфл — "
                "фисташка, маракуйя, карамель жана мисмиш. Тасмалуу кооз белек кабы, "
                "түз эле белекке берүүгө даяр.",
        desc_en="The perfect small gift 🤍 4 trayfl flavors in a compact box — "
                "pistachio, passion fruit, caramel and cherry. Beautifully "
                "gift-wrapped with a ribbon, ready to give right away.",
    ),
    dict(
        slug="bankeyki_2", price=750,
        name_ru="Банкейки, 2 вкуса в одной коробке",
        name_ky="Банкейки, 1 кутучада 2 даам",
        name_en="Bankeyki — 2 Flavors in One Box",
        desc_ru="Маленькие радости в красивой упаковке 🤍 2 баночных десерта "
                "разных вкусов в прозрачной коробке с лентой. Компактный формат "
                "— отличный вариант для небольшого презента.",
        desc_ky="Кооз кабында кичинекей кубанычтар 🤍 Тасмалуу тунук кутучада ар "
                "түрдүү даамдагы 2 банка десерт. Компакттуу формат — кичине белек "
                "үчүн эң ылайыктуу.",
        desc_en="Small joys in beautiful packaging 🤍 2 jar desserts in different "
                "flavors, in a clear box with a ribbon. A compact format — a great "
                "choice for a small gift.",
    ),
]


def run(*, dry_run: bool, branch_id: int, stock: int):
    branch = StoreBranch.objects.filter(id=branch_id).first()
    if branch is None:
        print(f"❌ Филиал id={branch_id} не найден.")
        sys.exit(1)
    store = branch.store
    print(f"Филиал: {branch} (id={branch.pk})")
    print(f"Магазин: {store} (id={store.pk})")

    category = StoreCategory.objects.filter(store=store, name_ru__icontains="трайфл").first()
    if category is None:
        category = StoreCategory.objects.filter(store=store).order_by("sort_order", "id").first()
    if category:
        print(f"Категория: {category} (id={category.pk})")
    else:
        print("⚠️  У магазина вообще нет категорий — товар будет без категории.")

    if dry_run:
        print("\n[DRY RUN] — в БД ничего не пишется.\n")

    created, skipped = 0, 0
    for p in PRODUCTS:
        exists = StoreProduct.objects.filter(store=store, name_ru=p["name_ru"]).exists()
        if exists:
            print(f"  ⏭  «{p['name_ru']}» уже есть в магазине — пропускаю.")
            skipped += 1
            continue

        print(f"  {'[DRY RUN] ' if dry_run else ''}+ «{p['name_ru']}» — {p['price']} сом "
              f"(фото: {p['slug']}.jpg, остаток на филиале: {stock})")
        if dry_run:
            created += 1
            continue

        with transaction.atomic():
            product = StoreProduct.objects.create(
                store=store, category=category,
                name_ru=p["name_ru"], name_ky=p["name_ky"], name_en=p["name_en"],
                description_ru=p["desc_ru"], description_ky=p["desc_ky"], description_en=p["desc_en"],
                price=Decimal(str(p["price"])),
                unit=StoreProduct.Unit.PCS,
                is_active=True, sell_direct=True,
            )
            photo_path = os.path.join(PHOTOS_DIR, f"{p['slug']}.jpg")
            if os.path.exists(photo_path):
                with open(photo_path, "rb") as f:
                    product.photo.save(f"{p['slug']}.jpg", ContentFile(f.read()), save=True)
            else:
                print(f"    ⚠  Фото не найдено: {photo_path}")

            StoreStock.objects.get_or_create(
                branch=branch, product=product,
                defaults=dict(qty=Decimal(str(stock))),
            )
        created += 1

    verb = "Будет создано" if dry_run else "Создано"
    print(f"\n✅ {verb}: {created}   Пропущено (уже есть): {skipped}")


def main():
    ap = argparse.ArgumentParser(description="Добавить новые товары в магазин Трайфл лавка")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--branch-id", type=int, default=41)
    ap.add_argument("--stock", type=int, default=5)
    args = ap.parse_args()
    run(dry_run=args.dry_run, branch_id=args.branch_id, stock=args.stock)


if __name__ == "__main__":
    main()
