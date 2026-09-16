"""
Добавляет цветы (по просьбе Султана из сообщения в WhatsApp) в магазин-цветочный —
категория «Цветы», с фото, ценой-заглушкой, коротким описанием и остатком по филиалу.

Идемпотентно: товар ищется по (store, name_ru) — повторный запуск не создаёт дублей,
только обновляет фото/цену (если она ещё не редактировалась вручную) и остаток.

ВАЖНО про фото: это НЕ реальные фото ваших букетов — это бесплатные (CC0/CC-BY,
без нарушения авторских прав) стоковые фото похожих цветов с Wikimedia Commons /
Openverse, подобранные вручную. Как только у вас будут свои фото — перезалейте их
через личный кабинет (там уже есть загрузка фото у каждого товара), это быстрее,
чем через скрипт.

ВАЖНО про цены: реальных цен не было в задаче — ниже проставлены ориентировочные
цены-заглушки (сом/шт). Обязательно поправьте их в личном кабинете после запуска!

Запуск на сервере (из корня проекта, где лежит manage.py):
    python manage.py add_flowers --branch-id 45 --photos-dir /путь/к/flower_photos

Сначала — репетиция без записи в БД:
    python manage.py add_flowers --branch-id 45 --photos-dir /путь/к/flower_photos --dry-run
"""

from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from shops.models import StoreBranch, StoreCategory, StoreProduct, StoreStock

CATEGORY_NAME = "Цветы"

# slug (имя файла фото без расширения) -> (название, цена-заглушка сом/шт, описание)
FLOWERS = [
    ("mahrovaya_eustoma", "Махровая эустома", 180,
     "Пышные махровые бутоны, похожие на маленькие розы — нежная альтернатива розе в букете."),
    ("eustoma", "Эустома", 150,
     "Изящная эустома (лизиантус) с тонкими лепестками — воздушный акцент для любого букета."),
    ("jumilia", "Джумилия", 90,
     "Кремово-персиковая роза сорта Джумилия — благородный оттенок для нежных композиций."),
    ("white_rose", "Белая роза", 70,
     "Классическая белая роза — символ чистоты, универсальна для любого повода."),
    ("red_rose", "Красная роза", 70,
     "Насыщенная красная роза — главный символ любви и признания в любом букете."),
    ("hydrangea_royal", "Королевская гортензия", 350,
     "Крупная пышная шапка гортензии — эффектный объёмный акцент дорогих букетов."),
    ("hydrangea_common", "Обычная гортензия", 280,
     "Гортензия классического голубого оттенка — плотное соцветие для объёма в букете."),
    ("eucalyptus", "Эвкалипт", 80,
     "Ароматная зелень эвкалипта — универсальное обрамление и заполнение букета."),
    ("rose_bush_sofia", 'Кустовая роза "София"', 120,
     "Кустовая (спрей) роза сорта София — сразу несколько бутонов на одном стебле."),
    ("lily", "Лилия", 200,
     "Крупная ароматная лилия — эффектный и статусный цветок для букета."),
    ("sunflower", "Подсолнух", 90,
     "Яркий солнечный подсолнух — позитивный акцент для летних и осенних букетов."),
    ("chrysanthemum", "Хризантема", 60,
     "Пышная хризантема-помпон — долго стоит в вазе, хороша и в букете, и поштучно."),
    ("dianthus", "Диантус", 50,
     "Диантус (гвоздика) с резными лепестками — яркий и неприхотливый цветок."),
    ("gerbera", "Гербера", 60,
     "Гербера — крупная ромашковидная головка насыщенного цвета, любимица ярких букетов."),
    ("limonium", "Лимониум", 70,
     "Лимониум (статица) — воздушная сухоцветная зелень-компаньон, долго сохраняет вид."),
]

DEFAULT_QTY = 25  # остаток на филиале — по просьбе "количество по 25 сделай"


class Command(BaseCommand):
    help = "Добавляет 15 видов цветов (категория «Цветы») в указанный филиал магазина, с фото и остатком"

    def add_arguments(self, parser):
        parser.add_argument("--branch-id", type=int, default=45,
                            help="ID филиала (StoreBranch), по умолчанию 45")
        parser.add_argument("--photos-dir", required=True,
                            help="Папка с фото: eustoma.jpg, red_rose.jpg и т.д. (см. список FLOWERS)")
        parser.add_argument("--qty", type=int, default=DEFAULT_QTY,
                            help=f"Остаток на филиале для каждого цветка (по умолчанию {DEFAULT_QTY})")
        parser.add_argument("--dry-run", action="store_true",
                            help="Только вывод, без записи в БД")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        photos_dir = Path(options["photos_dir"])
        qty = Decimal(str(options["qty"]))

        if not photos_dir.is_dir():
            raise CommandError(f"Папка с фото не найдена: {photos_dir}")

        try:
            branch = StoreBranch.objects.select_related("store").get(pk=options["branch_id"])
        except StoreBranch.DoesNotExist:
            raise CommandError(f"Филиал с id={options['branch_id']} не найден")

        store = branch.store
        self.stdout.write(f"Магазин: {store.name_ru} (id={store.pk}) — филиал: {branch.name_ru} (id={branch.pk})")

        category = None
        if not dry:
            category, created = StoreCategory.objects.get_or_create(
                store=store, name_ru=CATEGORY_NAME,
                defaults={"is_active": True},
            )
            self.stdout.write(f"{'Создана' if created else 'Найдена'} категория «{CATEGORY_NAME}» (id={category.pk})")

        created_n = updated_n = photo_n = missing_photo_n = 0

        for slug, name, price, description in FLOWERS:
            photo_path = None
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                p = photos_dir / f"{slug}{ext}"
                if p.exists():
                    photo_path = p
                    break

            self.stdout.write(
                f"  {name:<28} цена≈{price:>4} сом  фото: {photo_path.name if photo_path else '⚠️ НЕ НАЙДЕНО (' + slug + '.*)'}"
            )
            if not photo_path:
                missing_photo_n += 1
            if dry:
                continue

            product, created = StoreProduct.objects.get_or_create(
                store=store, name_ru=name,
                defaults={
                    "category": category,
                    "price": Decimal(str(price)),
                    "unit": StoreProduct.Unit.PCS,
                    "description_ru": description,
                    "is_active": True,
                },
            )
            if created:
                created_n += 1
            else:
                updated_n += 1
                changed = []
                if not product.category_id:
                    product.category = category
                    changed.append("category")
                if not product.description_ru:
                    product.description_ru = description
                    changed.append("description_ru")
                if changed:
                    product.save(update_fields=changed)

            if photo_path and not product.photo:
                with open(photo_path, "rb") as fh:
                    product.photo.save(photo_path.name, File(fh), save=True)
                photo_n += 1

            StoreStock.objects.update_or_create(
                branch=branch, product=product,
                defaults={"qty": qty, "is_stopped": False},
            )

        self.stdout.write(self.style.SUCCESS(
            f"\nГотово! Создано товаров: {created_n}, уже было (обновлено): {updated_n}, "
            f"фото загружено: {photo_n}, остаток выставлен: {qty} шт на филиал «{branch.name_ru}»"
        ))
        if missing_photo_n:
            self.stdout.write(self.style.WARNING(
                f"⚠️  Без фото осталось: {missing_photo_n} — файл не найден в {photos_dir}"
            ))
        self.stdout.write(self.style.WARNING(
            "⚠️  Цены — заглушки, проверьте и поправьте их в личном кабинете (Товары филиала)."
        ))
        if dry:
            self.stdout.write(self.style.WARNING("(dry-run — ничего не сохранено в БД)"))
