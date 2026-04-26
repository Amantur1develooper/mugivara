"""
One-time import script: парсит https://donbuton.kg/catalog/ и создаёт
магазин «Дон Бутон», категории и товары с загрузкой + сжатием фото.

Запуск:
    python manage.py import_donbuton
    python manage.py import_donbuton --store-id 5   # если магазин уже существует
    python manage.py import_donbuton --dry-run       # только вывод, без записи в БД
"""

import io
import time
import urllib.parse
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image

from shops.models import Store, StoreBranch, StoreCategory, StoreProduct, StoreStock

BASE_URL = "https://donbuton.kg"
CATALOG_URL = f"{BASE_URL}/catalog/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WeborodoImport/1.0)"}

# Сжатие: максимальный размер стороны и качество JPEG
MAX_SIZE = (800, 800)
JPEG_QUALITY = 82


def compress_image(raw_bytes: bytes, fmt: str = "JPEG") -> bytes:
    """Сжимает изображение: ресайз + оптимизация."""
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.thumbnail(MAX_SIZE, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def fetch(url: str, session: requests.Session) -> BeautifulSoup:
    r = session.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def get_all_product_links(session: requests.Session) -> list[dict]:
    """Собирает все ссылки на товары со всех страниц каталога."""
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

        # Есть ли следующая страница?
        next_link = soup.select_one(".pagination .page-link[href*='page=']")
        page_links = soup.select(".pagination .page-link")
        nums = [p.get_text(strip=True) for p in page_links if p.get_text(strip=True).isdigit()]
        last_page = max(int(n) for n in nums) if nums else 1
        if page >= last_page:
            break
        page += 1
        time.sleep(0.5)

    return items


def parse_product_detail(url: str, category_hint: str, session: requests.Session) -> dict | None:
    """Парсит страницу товара и возвращает словарь с данными."""
    try:
        soup = fetch(url, session)
    except Exception as e:
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
        raw = price_el.get_text(strip=True).replace("\xa0", "").replace(" ", "").replace("сом", "").replace(",", ".")
        # Оставляем только цифры и точку
        import re
        m = re.search(r"[\d]+\.?\d*", raw)
        if m:
            try:
                price = Decimal(m.group())
            except InvalidOperation:
                pass

    # Описание
    desc_el = soup.select_one(".product-description")
    description = desc_el.get_text(strip=True) if desc_el else ""

    # Категория из мета-блока на детальной странице
    cat_meta = soup.select_one(".product-meta .meta-item")
    category = category_hint
    if cat_meta:
        text = cat_meta.get_text(separator=" ", strip=True)
        if "Категория" in text:
            # текст вида "Категория: Белые Розы"
            parts = text.split(":", 1)
            if len(parts) == 2:
                category = parts[1].strip()

    # Главное фото
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
        "source_url": url,
    }


class Command(BaseCommand):
    help = "Импортирует товары с сайта donbuton.kg в магазин «Дон Бутон»"

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, default=None,
                            help="ID существующего Store (если не указан — будет создан)")
        parser.add_argument("--branch-id", type=int, default=None,
                            help="ID существующего StoreBranch (если не указан — будет создан)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Только парсинг, без записи в БД и без скачивания фото")
        parser.add_argument("--delay", type=float, default=0.7,
                            help="Задержка между запросами в секундах (по умолчанию 0.7)")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        delay = options["delay"]
        session = requests.Session()

        # ── 1. Магазин ──────────────────────────────────────────────────
        if options["store_id"]:
            store = Store.objects.get(pk=options["store_id"])
            self.stdout.write(f"Используется существующий магазин: {store}")
        elif not dry:
            store, created = Store.objects.get_or_create(
                slug="don-buton",
                defaults={
                    "name_ru": "Дон Бутон",
                    "about_ru": "Уютный цветочный магазин в Оше. Свежие букеты, авторские композиции и доставка цветов по городу.",
                    "instagram_url": "https://www.instagram.com/donbuton.kg",
                },
            )
            self.stdout.write(f"{'Создан' if created else 'Найден'} магазин: {store}")
        else:
            store = None

        # ── 2. Филиал ───────────────────────────────────────────────────
        if options["branch_id"]:
            branch = StoreBranch.objects.get(pk=options["branch_id"])
            self.stdout.write(f"Используется существующий филиал: {branch}")
        elif not dry and store:
            branch, created = StoreBranch.objects.get_or_create(
                store=store,
                name_ru="Дон Бутон — Ош",
                defaults={
                    "city": StoreBranch.City.OSH,
                    "address": "г. Ош",
                    "phone": "+996508801055",
                    "delivery_enabled": True,
                    "is_active": True,
                },
            )
            self.stdout.write(f"{'Создан' if created else 'Найден'} филиал: {branch}")
        else:
            branch = None

        # ── 3. Сбор ссылок ──────────────────────────────────────────────
        self.stdout.write("Собираю список товаров...")
        product_links = get_all_product_links(session)
        self.stdout.write(f"Найдено ссылок: {len(product_links)}")

        # ── 4. Парсинг и импорт ─────────────────────────────────────────
        categories: dict[str, StoreCategory | None] = {}
        imported = 0
        skipped = 0

        for i, item in enumerate(product_links, 1):
            time.sleep(delay)
            data = parse_product_detail(item["url"], item["category"], session)
            if not data:
                self.stdout.write(self.style.WARNING(f"  [{i}] Не удалось спарсить: {item['url']}"))
                skipped += 1
                continue

            self.stdout.write(
                f"  [{i}/{len(product_links)}] {data['title'][:55]:55s} | "
                f"{data['price']:>8} сом | {data['category']}"
            )

            if dry:
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
            cat_obj = categories[cat_name]

            # Товар — обновляем если уже существует (по названию)
            product, created = StoreProduct.objects.get_or_create(
                store=store,
                name_ru=data["title"],
                defaults={
                    "category": cat_obj,
                    "description_ru": data["description"],
                    "price": data["price"],
                    "unit": StoreProduct.Unit.PCS,
                    "is_active": True,
                },
            )
            if not created:
                # обновляем цену и описание при повторном запуске
                product.price = data["price"]
                product.description_ru = data["description"]
                product.category = cat_obj
                product.save(update_fields=["price", "description_ru", "category"])

            # Фото: скачиваем и сжимаем только если ещё нет
            if data["img_url"] and not product.photo:
                try:
                    resp = session.get(data["img_url"], headers=HEADERS, timeout=20)
                    resp.raise_for_status()
                    compressed = compress_image(resp.content)
                    # Имя файла из URL
                    fname = urllib.parse.unquote(data["img_url"].split("/")[-1])
                    if not fname.lower().endswith((".jpg", ".jpeg")):
                        fname = fname.rsplit(".", 1)[0] + ".jpg"
                    product.photo.save(fname, ContentFile(compressed), save=True)
                    self.stdout.write(f"       фото сохранено: {fname} ({len(compressed)//1024} KB)")
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"       фото не загружено: {e}"))

            # Остаток на складе (если филиал есть)
            if branch:
                StoreStock.objects.get_or_create(
                    branch=branch,
                    product=product,
                    defaults={"qty": 999},
                )

            imported += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nГотово! Импортировано: {imported}, пропущено: {skipped}"
        ))
        if dry:
            self.stdout.write(self.style.WARNING("(dry-run — ничего не сохранено)"))
