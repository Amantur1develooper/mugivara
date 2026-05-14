"""
python manage.py import_daamordo          # полный импорт
python manage.py import_daamordo --dry-run # только парсинг, без записи в БД
"""

import json
import os
import re
from html import unescape
from io import BytesIO

import requests
from django.core.management.base import BaseCommand


def _decode(node):
    """Decode Astro's [tag, value] serialisation recursively."""
    if isinstance(node, list):
        if (len(node) == 2
                and isinstance(node[0], int)
                and node[0] in (0, 1)):
            tag, val = node
            if tag == 0:
                return _decode(val)
            else:           # tag == 1  →  array
                return [_decode(x) for x in val]
        # plain list (no tag)
        return [_decode(x) for x in node]
    if isinstance(node, dict):
        return {k: _decode(v) for k, v in node.items()}
    return node


def _compress(url, max_side=900, quality=82):
    """Download + compress to WebP. Returns (ContentFile, filename) or (None, None)."""
    from io import BytesIO
    from PIL import Image
    from django.core.files.base import ContentFile
    if not url:
        return None, None
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, "WEBP", quality=quality, method=6)
        buf.seek(0)
        base = os.path.splitext(os.path.basename(url.split("?")[0]))[0]
        return ContentFile(buf.read()), f"{base}.webp"
    except Exception as e:
        return None, str(e)


class Command(BaseCommand):
    help = "Import daamordo.kg → creates Restaurant + full menu"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Parse only, do NOT write to DB")
        parser.add_argument("--no-images", action="store_true",
                            help="Skip image download (faster)")

    def log(self, msg):
        self.stdout.write(msg)

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def err(self, msg):
        self.stdout.write(self.style.ERROR(msg))

    def handle(self, *args, **options):
        dry      = options["dry_run"]
        no_img   = options["no_images"]

        # ── 1. Fetch HTML ────────────────────────────────────────────────────
        self.log("📡 Fetching https://daamordo.kg/ ...")
        try:
            resp = requests.get(
                "https://daamordo.kg/",
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"   # force correct encoding
            self.ok(f"   HTTP {resp.status_code}  ({len(resp.text)} chars)")
        except Exception as e:
            self.err(f"FETCH ERROR: {e}")
            return

        # ── 2. Find astro-island props ───────────────────────────────────────
        # Try several patterns in case markup differs
        html = resp.text
        m = (
            re.search(r'<astro-island[^>]+\bprops="([^"]+)"', html)
            or re.search(r'\bprops="(\{[^"]+\})"', html)
        )
        if not m:
            self.err("Could not find props= in HTML. Saving page to /tmp/daamordo.html for inspection.")
            with open("/tmp/daamordo.html", "w") as f:
                f.write(html)
            return

        raw_props = unescape(m.group(1))
        self.log(f"   props snippet: {raw_props[:120]} ...")

        # ── 3. Parse JSON ────────────────────────────────────────────────────
        try:
            props_json = json.loads(raw_props)
        except json.JSONDecodeError as e:
            self.err(f"JSON parse error: {e}")
            self.err(f"Raw (first 300): {raw_props[:300]}")
            return

        decoded = _decode(props_json)
        self.log(f"   decoded top-level keys: {list(decoded.keys()) if isinstance(decoded, dict) else type(decoded)}")

        # Navigate to data root (handle both {data: ...} and direct dict)
        data = decoded
        if isinstance(decoded, dict):
            data = decoded.get("data") or decoded

        if not isinstance(data, dict):
            self.err(f"Unexpected data type after decode: {type(data)}. Value: {str(data)[:200]}")
            return

        categories_raw = data.get("categories", [])
        items_raw      = data.get("menu_items") or data.get("items", [])

        self.log(f"   data keys            : {list(data.keys())}")
        self.log(f"   categories raw count : {len(categories_raw)}")
        self.log(f"   items raw count      : {len(items_raw)}")

        if not categories_raw or not items_raw:
            self.err("No categories or items found.")
            return

        # Print sample to verify parsing
        self.log("\n📋 Sample category[0]:")
        self.log(f"   {categories_raw[0] if categories_raw else 'EMPTY'}")
        self.log("\n📋 Sample item[0]:")
        self.log(f"   {items_raw[0] if items_raw else 'EMPTY'}")

        if dry:
            self.ok("\n✅ DRY RUN complete — no DB writes.")
            return

        # ── 4. DB Imports ────────────────────────────────────────────────────
        from catalog.models import (
            BranchCategory, BranchCategoryItem, BranchItem,
            BranchMenuSet, Category, Item, ItemCategory, MenuSet,
        )
        from core.models import Branch, Restaurant

        # Restaurant
        from django.utils.text import slugify
        import uuid

        restaurant, created = Restaurant.objects.get_or_create(
            slug="daamordo",
            defaults={"name_ru": "Daamordo", "is_active": True},
        )
        self.ok(f"\n{'✨ Created' if created else '♻️  Found'} Restaurant id={restaurant.id}")

        branch, _ = Branch.objects.get_or_create(
            restaurant=restaurant, name_ru="Daamordo",
            defaults={"is_active": True},
        )
        self.log(f"   Branch id={branch.id}")

        menu_set, _ = MenuSet.objects.get_or_create(
            restaurant=restaurant, name="Основное меню",
            defaults={"is_active": True},
        )
        BranchMenuSet.objects.get_or_create(branch=branch, menu_set=menu_set)
        self.log(f"   MenuSet id={menu_set.id}")

        # Categories
        self.log(f"\n📂 Creating {len(categories_raw)} categories...")
        cat_map = {}  # src_id → (Category, BranchCategory)
        for i, raw in enumerate(categories_raw):
            if not isinstance(raw, dict):
                self.err(f"   skip cat #{i}: not a dict → {raw}")
                continue
            src_id  = raw.get("id")
            name_ru = (raw.get("name") or {}).get("ru") or f"Категория {i+1}"
            cat, _ = Category.objects.get_or_create(
                menu_set=menu_set, name_ru=name_ru,
            )
            bc, _ = BranchCategory.objects.get_or_create(
                branch=branch, category=cat,
                defaults={"sort_order": i, "is_active": True},
            )
            cat_map[src_id] = (cat, bc)
            self.log(f"   [{i+1}] id={src_id} → {name_ru}")

        self.ok(f"   ✅ {len(cat_map)} categories ready")

        # Items
        self.log(f"\n🍽  Creating {len(items_raw)} items...")
        created_count = 0
        img_ok = 0
        img_fail = 0

        for idx, raw in enumerate(items_raw):
            if not isinstance(raw, dict):
                self.err(f"   skip item #{idx}: not a dict")
                continue

            name_ru   = (raw.get("name") or {}).get("ru") or ""
            desc_ru   = (raw.get("description") or {}).get("ru") or ""
            price     = raw.get("price") or 0
            image_url = raw.get("image_url") or ""
            cat_id    = raw.get("category_id")
            sort_ord  = raw.get("sort_order") or idx

            if not name_ru:
                self.log(f"   [{idx+1}] skip — empty name")
                continue

            # Item
            item, item_new = Item.objects.get_or_create(
                restaurant=restaurant,
                name_ru=name_ru,
                defaults={"description_ru": desc_ru, "base_price": price},
            )
            if not item_new:
                item.description_ru = desc_ru
                item.base_price = price

            # Photo
            if image_url and not item.photo and not no_img:
                content, fname_or_err = _compress(image_url)
                if content:
                    item.photo.save(fname_or_err, content, save=False)
                    img_ok += 1
                    status = "✅"
                else:
                    img_fail += 1
                    status = f"⚠️ img fail: {fname_or_err}"
            else:
                status = "—" if no_img else ("↩ photo exists" if item.photo else "no url")

            item.save()

            # BranchItem
            bi, _ = BranchItem.objects.get_or_create(
                branch=branch, item=item,
                defaults={"price": price, "sort_order": sort_ord, "is_available": True},
            )
            if not _:
                bi.price = price
                bi.save(update_fields=["price"])

            # Link to category
            if cat_id in cat_map:
                cat, bc = cat_map[cat_id]
                ItemCategory.objects.get_or_create(
                    item=item, category=cat,
                    defaults={"sort_order": sort_ord},
                )
                BranchCategoryItem.objects.get_or_create(
                    branch_category=bc, branch_item=bi,
                    defaults={"sort_order": sort_ord},
                )
            else:
                self.err(f"   [{idx+1}] cat_id={cat_id} NOT in cat_map ({list(cat_map.keys())})")

            created_count += 1
            self.log(f"   [{idx+1}/{len(items_raw)}] {name_ru} | {price} сом | {status}")

        # Summary
        self.stdout.write("")
        self.ok("=" * 55)
        self.ok("✅  Import complete!")
        self.log(f"   Restaurant : Daamordo  (id={restaurant.id})")
        self.log(f"   Branch     : id={branch.id}")
        self.log(f"   Categories : {len(cat_map)}")
        self.log(f"   Items      : {created_count}")
        self.log(f"   Photos     : {img_ok} ok / {img_fail} failed")
        self.ok("=" * 55)
        self.log("")
        self.log("📌 If you haven't linked your account yet:")
        self.log("   python manage.py shell")
        self.log("   from core.models import Restaurant, Membership")
        self.log("   from django.contrib.auth.models import User")
        self.log("   u = User.objects.get(username='ВАШ_ЛОГИН')")
        self.log("   r = Restaurant.objects.get(slug='daamordo')")
        self.log("   Membership.objects.get_or_create(user=u, restaurant=r)")
