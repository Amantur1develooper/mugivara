# -*- coding: utf-8 -*-
"""Заводит чайхану «Zire» (Ош) вместе со всем меню.

Меню сняли со сторис заведения — 41 страница. Названия, цены и составы
разобраны по страницам и лежат рядом в _zire_menu/menu.json, фотографии
блюд вырезаны оттуда же в _zire_menu/photos. Команда переносит это в базу:
заведение, филиал, разделы, блюда, цены и фото — на трёх языках.

    python manage.py import_zire --dry-run    посмотреть, что будет заведено
    python manage.py import_zire              завести
    python manage.py import_zire --no-photos  без фотографий
    python manage.py import_zire --reset      удалить прежнее и завести заново

Повторный запуск ничего не дублирует: блюда ищутся по названию, у
найденных дозаполняются пустые поля. Так поправленную руками цену или
описание команда не затирает.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

DATA = Path(__file__).resolve().parent / "_zire_menu"
SLUG = "zire-osh"


class Command(BaseCommand):
    help = "Заводит чайхану «Zire» (Ош) с полным меню"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="только показать, без записи в базу")
        parser.add_argument("--no-photos", action="store_true",
                            help="не прикреплять фотографии блюд")
        parser.add_argument("--reset", action="store_true",
                            help="удалить заведение и завести заново")

    # ── данные ──────────────────────────────────────────────────────────────

    def _load(self):
        menu_file, venue_file = DATA / "menu.json", DATA / "venue.json"
        if not menu_file.exists():
            raise CommandError(f"Нет файла меню: {menu_file}")
        dishes = json.loads(menu_file.read_text(encoding="utf-8"))
        venue = json.loads(venue_file.read_text(encoding="utf-8"))

        # Разделы идут в том порядке, в каком встречаются в меню: так
        # на сайте они и выстроятся — завтраки сверху, напитки внизу.
        cats, seen = [], set()
        for d in dishes:
            if d["cat_ru"] not in seen:
                seen.add(d["cat_ru"])
                cats.append((d["cat_ru"], d.get("cat_ky", ""), d.get("cat_en", "")))
        return venue, cats, dishes

    def _set_image(self, obj, field, path, filename):
        """Кладёт картинку в пустое поле модели. Занятое оставляет как есть."""
        if not path.exists() or getattr(obj, field):
            return False
        getattr(obj, field).save(filename, ContentFile(path.read_bytes()), save=True)
        self.stdout.write(f"  {field}: {filename}")
        return True

    # ── запуск ──────────────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        ok, warn = self.style.SUCCESS, self.style.WARNING
        venue, cats, dishes = self._load()
        photos = sum(1 for d in dishes if (DATA / "photos" / f"{d['slug']}.jpg").exists())

        self.stdout.write(f"Заведение : {venue['name_ru']} {venue['kind']}, {venue['city']}")
        self.stdout.write(f"Разделов  : {len(cats)}")
        self.stdout.write(f"Блюд      : {len(dishes)}")
        self.stdout.write(f"Фото      : {photos}"
                          + (" (пропускаю)" if opts["no_photos"] else ""))

        if opts["dry_run"]:
            for name_ru, name_ky, name_en in cats:
                items = [d for d in dishes if d["cat_ru"] == name_ru]
                self.stdout.write(f"\n  {name_ru} / {name_ky} / {name_en} — {len(items)}")
                for d in items:
                    mark = "📷" if (DATA / "photos" / f"{d['slug']}.jpg").exists() else "  "
                    self.stdout.write(f"    {mark} {d['name_ru']} — {d['price']} сом")
            self.stdout.write(warn("\nЭто только список. Чтобы завести, повторите без --dry-run"))
            return

        from catalog.models import (BranchCategory, BranchCategoryItem, BranchItem,
                                    BranchMenuSet, Category, Item, ItemCategory, MenuSet)
        from core.models import Branch, Restaurant

        if opts["reset"]:
            n, _ = Restaurant.objects.filter(slug=SLUG).delete()
            self.stdout.write(f"Удалено записей: {n}")

        full_name = f"{venue['name_ru']} {venue['kind']}"
        rest, rest_new = Restaurant.objects.get_or_create(
            slug=SLUG,
            defaults={
                "name_ru": full_name, "name_ky": full_name, "name_en": f"{venue['name_en']} Chaikhana",
                "about_ru": venue.get("about_ru", ""),
                "about_ky": venue.get("about_ky", ""),
                "about_en": venue.get("about_en", ""),
                "phone": venue.get("phone", ""),
                "instagram": (f"https://instagram.com/{venue['instagram']}"
                              if venue.get("instagram") else ""),
                "is_active": True,
            },
        )
        self.stdout.write(ok(f"\nЗаведение #{rest.id} — {'создано' if rest_new else 'уже было'}"))

        # Логотип и обложка — с титульной страницы меню. Ставим только в
        # пустое поле: загруженную заведением картинку не трогаем.
        if not opts["no_photos"]:
            self._set_image(rest, "logo", DATA / "logo.jpg", "zire-logo.jpg")
            self._set_image(rest, "cover", DATA / "cover.jpg", "zire-cover.jpg")

        branch, _ = Branch.objects.get_or_create(
            restaurant=rest, name_ru=f"{venue['name_ru']}, {venue['city']}",
            defaults={
                "name_ky": f"{venue['name_ru']}, {venue['city']}",
                "name_en": f"{venue['name_en']}, Osh",
                "address": venue.get("address", ""),
                "phone": venue.get("phone", ""),
                "open_time": venue.get("open_time") or "07:00",
                "close_time": venue.get("close_time") or "02:00",
                "work_days": "0,1,2,3,4,5,6",
                "is_active": True,
            },
        )
        if not opts["no_photos"]:
            self._set_image(branch, "cover_photo", DATA / "cover.jpg", "zire-cover.jpg")

        menu_set, _ = MenuSet.objects.get_or_create(
            restaurant=rest, name="Основное меню", defaults={"is_active": True})
        BranchMenuSet.objects.get_or_create(branch=branch, menu_set=menu_set)
        self.stdout.write(f"Филиал #{branch.id}, меню #{menu_set.id}")

        cat_by_name, bcat_by_name = {}, {}
        for i, (name_ru, name_ky, name_en) in enumerate(cats):
            cat, _ = Category.objects.get_or_create(
                menu_set=menu_set, name_ru=name_ru,
                defaults={"name_ky": name_ky, "name_en": name_en})
            bcat, _ = BranchCategory.objects.get_or_create(
                branch=branch, category=cat,
                defaults={"sort_order": i * 10, "is_active": True})
            cat_by_name[name_ru], bcat_by_name[name_ru] = cat, bcat
        self.stdout.write(f"Разделов заведено: {len(cat_by_name)}")

        created = filled = with_photo = 0
        for i, d in enumerate(dishes):
            price = Decimal(str(d["price"]))
            item, is_new = Item.objects.get_or_create(
                restaurant=rest, name_ru=d["name_ru"],
                defaults={
                    "name_ky": d.get("name_ky", ""), "name_en": d.get("name_en", ""),
                    "description_ru": d.get("desc_ru", ""),
                    "description_ky": d.get("desc_ky", ""),
                    "description_en": d.get("desc_en", ""),
                    "base_price": price,
                },
            )
            if is_new:
                created += 1
            else:
                # Пустые поля дозаполняем, заполненные не трогаем: их могли
                # поправить руками после первого запуска.
                changed = []
                for field, value in (("name_ky", d.get("name_ky", "")),
                                     ("name_en", d.get("name_en", "")),
                                     ("description_ru", d.get("desc_ru", "")),
                                     ("description_ky", d.get("desc_ky", "")),
                                     ("description_en", d.get("desc_en", ""))):
                    if value and not getattr(item, field):
                        setattr(item, field, value)
                        changed.append(field)
                if changed:
                    item.save(update_fields=changed)
                    filled += 1

            photo = DATA / "photos" / f"{d['slug']}.jpg"
            if not opts["no_photos"] and photo.exists() and not item.photo:
                item.photo.save(f"zire-{d['slug']}.jpg",
                                ContentFile(photo.read_bytes()), save=True)
                with_photo += 1

            bi, _ = BranchItem.objects.get_or_create(
                branch=branch, item=item,
                defaults={"price": price, "is_available": True})
            ItemCategory.objects.get_or_create(
                item=item, category=cat_by_name[d["cat_ru"]],
                defaults={"sort_order": i})
            BranchCategoryItem.objects.get_or_create(
                branch_category=bcat_by_name[d["cat_ru"]], branch_item=bi,
                defaults={"sort_order": i})

        self.stdout.write(ok(f"\nГотово. Блюд создано: {created}, дозаполнено: {filled}, "
                             f"фотографий прикреплено: {with_photo}."))
        self.stdout.write(f"Меню: /ru/r/{SLUG}/  ·  филиал #{branch.id}")
