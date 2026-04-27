#!/usr/bin/env python
"""
Standalone скрипт импорта товаров с сайта donbuton.kg.

Запуск (из корня проекта, где manage.py):
    python import_donbuton_standalone.py

Или с параметрами:
    python import_donbuton_standalone.py --dry-run        # тест без записи в БД
    python import_donbuton_standalone.py --store-id 5     # использовать существующий магазин
    python import_donbuton_standalone.py --branch-id 3    # использовать существующий филиал
    python import_donbuton_standalone.py --delay 1.0      # задержка между запросами

Требования: pip install requests beautifulsoup4 lxml pillow
"""

import argparse
import io
import os
import sys
import time
import urllib.parse
import re
from decimal import Decimal, InvalidOperation

# ── Настройка Django окружения ───────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()
# ────────────────────────────────────────────────────────────────────────────

import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from PIL import Image

from shops.models import Store, StoreBranch, StoreCategory, StoreProduct, StoreStock

BASE_URL = "https://donbuton.kg"
CATALOG_URL = f"{BASE_URL}/catalog/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WeborodoImport/1.0)"}

# Сжатие фото: максимальный размер стороны и качество JPEG
MAX_SIZE = (800, 800)
JPEG_QUALITY = 82


def compress_image(raw_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.thumbnail(MAX_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def fetch(url: str, session: requests.Session) -> BeautifulSoup:
    r = session.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def get_all_product_links(session: requests.Session) -> list:
    items = []
    page = 1
    while True:
        url = f"{CATALOG_URL}?page={page}"
        soup = fetch(url, session)
        cards = soup.select(".product-card")
        if not cards:
            break

        for card in cards:
            link_el = card.select_one("a[href]")
            badge = card.select_one(".product-badge")
            if not link_el:
                continue
            href = link_el["href"]
            if not href.startswith("http"):
                href = BASE_URL + href
            items.append({
                "url": href,
                "category": badge.get_text(strip=True) if badge else "Без категории",
            })

        page_links = soup.select(".pagination .page-link")
        nums = [p.get_text(strip=True) for p in page_links if p.get_text(strip=True).isdigit()]
        last_page = max(int(n) for n in nums) if nums else 1
        if page >= last_page:
            break
        page += 1
        time.sleep(0.4)

    return items


def parse_product_detail(url: str, category_hint: str, session: requests.Session):
    try:
        soup = fetch(url, session)
    except Exception as e:
        print(f"  ОШИБКА при загрузке {url}: {e}")
        return None

    title_el = soup.select_one("h1.product-title, .product-detail h1, .product-title")
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        return None

    # Цена
    price = Decimal("0")
    price_el = soup.select_one(".regular-price, .final-price, .product-price-section .final-price")
    if not price_el:
        price_el = soup.select_one("[class*=price]")
    if price_el:
        raw = (price_el.get_text(strip=True)
               .replace("\xa0", "").replace(" ", "")
               .replace("сом", "").replace(",", "."))
        m = re.search(r"[\d]+\.?\d*", raw)
        if m:
            try:
                price = Decimal(m.group())
            except InvalidOperation:
                pass

    # Описание
    desc_el = soup.select_one(".product-description")
    description = desc_el.get_text(strip=True) if desc_el else ""

    # Категория из мета-блока
    category = category_hint
    cat_meta = soup.select_one(".product-meta .meta-item")
    if cat_meta:
        text = cat_meta.get_text(separator=" ", strip=True)
        if "Категория" in text:
            parts = text.split(":", 1)
            if len(parts) == 2:
                category = parts[1].strip()

    # Фото
    img_url = None
    img_el = soup.select_one(".main-image, .product-gallery img, .product-img-container img")
    if img_el and img_el.get("src"):
        src = img_el["src"]
        img_url = src if src.startswith("http") else BASE_URL + src

    return {
        "title": title,
        "price": price,
        "description": description,
        "category": category,
        "img_url": img_url,
    }


def run(store_id=None, branch_id=None, dry_run=False, delay=0.7,
        store_name=None, store_slug=None, branch_name=None):
    session = requests.Session()

    # ── 1. Магазин ──────────────────────────────────────────────────────────
    if store_id:
        store = Store.objects.get(pk=store_id)
        print(f"Используется существующий магазин: {store}")
    elif not dry_run:
        # Если передано своё имя/slug — создаём новый магазин, не ищем старый
        slug = store_slug or "don-buton"
        name = store_name or "Дон Бутон"
        store, created = Store.objects.get_or_create(
            slug=slug,
            defaults={
                "name_ru": name,
                "about_ru": (
                    "Уютный цветочный магазин в Оше. "
                    "Свежие букеты, авторские композиции и доставка цветов по городу."
                ),
                "instagram_url": "https://www.instagram.com/donbuton.kg",
            },
        )
        print(f"{'Создан' if created else 'Найден'} магазин: {store} (id={store.pk})")
    else:
        store = None

    # ── 2. Филиал ────────────────────────────────────────────────────────────
    if branch_id:
        branch = StoreBranch.objects.get(pk=branch_id)
        print(f"Используется существующий филиал: {branch}")
    elif not dry_run and store:
        b_name = branch_name or store.name_ru + " — Ош"
        branch, created = StoreBranch.objects.get_or_create(
            store=store,
            name_ru=b_name,
            defaults={
                "city": StoreBranch.City.OSH,
                "address": "г. Ош",
                "phone": "+996508801055",
                "delivery_enabled": True,
                "is_active": True,
            },
        )
        print(f"{'Создан' if created else 'Найден'} филиал: {branch} (id={branch.pk})")
    else:
        branch = None

    # ── 3. Сбор ссылок ───────────────────────────────────────────────────────
    print("\nСобираю список товаров...")
    product_links = get_all_product_links(session)
    print(f"Найдено ссылок: {len(product_links)}\n")

    # ── 4. Парсинг и импорт ──────────────────────────────────────────────────
    categories = {}
    imported = 0
    skipped = 0

    for i, item in enumerate(product_links, 1):
        time.sleep(delay)
        data = parse_product_detail(item["url"], item["category"], session)
        if not data:
            print(f"  [{i}/{len(product_links)}] ПРОПУЩЕН: {item['url']}")
            skipped += 1
            continue

        print(
            f"  [{i:>2}/{len(product_links)}] "
            f"{data['title'][:52]:52s} | "
            f"{str(data['price']):>9} сом | {data['category']}"
        )

        if dry_run:
            continue

        # Категория
        cat_name = data["category"] or "Без категории"
        if cat_name not in categories:
            cat_obj, _ = StoreCategory.objects.get_or_create(
                store=store,
                name_ru=cat_name,
                defaults={"sort_order": len(categories) * 10},
            )
            categories[cat_name] = cat_obj

        # Товар — всегда новая запись если магазин новый,
        # иначе обновляем существующий по имени
        existing = StoreProduct.objects.filter(store=store, name_ru=data["title"]).first()
        if existing:
            existing.price = data["price"]
            existing.description_ru = data["description"]
            existing.category = categories[cat_name]
            existing.save(update_fields=["price", "description_ru", "category"])
            product = existing
        else:
            product = StoreProduct.objects.create(
                store=store,
                name_ru=data["title"],
                category=categories[cat_name],
                description_ru=data["description"],
                price=data["price"],
                unit=StoreProduct.Unit.PCS,
                is_active=True,
            )

        # Фото: скачиваем и сжимаем только если ещё нет
        if data["img_url"] and not product.photo:
            try:
                resp = session.get(data["img_url"], headers=HEADERS, timeout=20)
                resp.raise_for_status()
                compressed = compress_image(resp.content)
                fname = urllib.parse.unquote(data["img_url"].split("/")[-1])
                if not fname.lower().endswith((".jpg", ".jpeg")):
                    fname = fname.rsplit(".", 1)[0] + ".jpg"
                product.photo.save(fname, ContentFile(compressed), save=True)
                print(f"       фото: {fname} ({len(compressed) // 1024} KB)")
            except Exception as e:
                print(f"       фото НЕ загружено: {e}")

        # Остаток на складе
        if branch:
            StoreStock.objects.get_or_create(
                branch=branch,
                product=product,
                defaults={"qty": 999},
            )

        imported += 1

    print(f"\n{'='*60}")
    print(f"Готово! Импортировано: {imported}, пропущено: {skipped}")
    if dry_run:
        print("(dry-run — ничего не сохранено в БД)")
    if store and not dry_run:
        print(f"Магазин ID={store.pk}, Филиал ID={branch.pk if branch else '—'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Импорт товаров с donbuton.kg → Webordo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Первый раз (создаёт магазин "Дон Бутон"):
  python import_donbuton_standalone.py

  # Создать второй магазин с другим именем:
  python import_donbuton_standalone.py --store-name "Дон Бутон 2" --store-slug don-buton-2

  # Загрузить в уже существующий магазин по ID:
  python import_donbuton_standalone.py --store-id 5

  # Тест без записи в БД:
  python import_donbuton_standalone.py --dry-run
        """
    )
    parser.add_argument("--store-id",    type=int,   default=None,  help="ID существующего магазина")
    parser.add_argument("--branch-id",   type=int,   default=None,  help="ID существующего филиала")
    parser.add_argument("--store-name",  type=str,   default=None,  help='Название нового магазина, например "Дон Бутон 2"')
    parser.add_argument("--store-slug",  type=str,   default=None,  help='Slug нового магазина, например don-buton-2')
    parser.add_argument("--branch-name", type=str,   default=None,  help='Название нового филиала')
    parser.add_argument("--dry-run",     action="store_true",        help="Только парсинг, без записи в БД")
    parser.add_argument("--delay",       type=float, default=0.7,   help="Задержка между запросами (сек)")
    args = parser.parse_args()

    run(
        store_id=args.store_id,
        branch_id=args.branch_id,
        dry_run=args.dry_run,
        delay=args.delay,
        store_name=args.store_name,
        store_slug=args.store_slug,
        branch_name=args.branch_name,
    )
