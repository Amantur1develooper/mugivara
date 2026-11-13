"""Барбершоп «Barber House» (Ош) — прайс с афиши заведения.

Команда идемпотентна: повторный запуск обновляет цены и переводы, а не плодит
дубли. Услуги ищутся по названию внутри своего барбершопа.

    python manage.py import_barber_house
    python manage.py import_barber_house --owner artur   # выдать доступ в кабинет
    python manage.py import_barber_house --dry-run
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from barbershop.models import (
    Barbershop, BarbershopMembership, ServiceCategory, Service,
    Barber, BarberSchedule, BarberService,
)

SLUG = "barber-house-osh"

SHOP = {
    "name":          "Barber House",
    "name_en":       "Barber House",
    "tagline":       "Мужской барбершоп в Оше",
    "tagline_en":    "Men's barbershop in Osh",
    "description":   "В продаже: мужская косметика, укладочные средства, подарочные сертификаты.\n"
                     "Instagram: @barber_house.osh",
    "description_en": "In store: men's cosmetics, styling products, gift certificates.\n"
                      "Instagram: @barber_house.osh",
    "address":       "г. Ош",
    "phone":         "+996557440606",
    "whatsapp":      "996557440606",
    "working_hours": "",          # заполнит владелец в кабинете
    "is_active":     True,
    "sort_order":    0,
}

# (категория, en, порядок) → [(услуга, en, цена, минуты, описание, описание_en)]
CATALOG = [
    ("Основные услуги", "Main services", 10, [
        ("Мужская стрижка", "Men's haircut", 500, 40, "", ""),
        ("Детская стрижка (с 3 до 12 лет)", "Kids' haircut (3–12 years)", 300, 30, "", ""),
        ("Стрижка под машинку (одна насадка)", "Clipper cut (one guard)", 250, 20, "", ""),
        ("Стрижка под машинку (несколько насадок)", "Clipper cut (several guards)", 400, 30, "", ""),
        ("Окантовка", "Edge-up", 200, 15, "", ""),
        ("Королевское бритьё (голова или лицо)", "Royal shave (head or face)", 500, 30, "", ""),
        ("Моделирование бороды", "Beard shaping", 400, 25, "", ""),
        ("Удлинённая стрижка", "Long haircut", 700, 50, "", ""),
    ]),
    ("Дополнительные услуги", "Additional services", 20, [
        ("Мытьё и укладка волос", "Wash and styling", 200, 20, "", ""),
        ("Камуфляж седины (голова)", "Grey camouflage (hair)", 500, 30, "", ""),
        ("Камуфляж седины (борода)", "Grey camouflage (beard)", 400, 20, "", ""),
        ("Спа / чистка лица", "Facial spa and cleansing", 500, 30, "", ""),
        ("Хим. завивка", "Perm", 1500, 90, "", ""),
        ("Удаление волос воском", "Waxing", 100, 15,
         "От 100 до 500 сом — зависит от зоны", "From 100 to 500 KGS — depends on the area"),
        ("Hair Tattoo", "Hair tattoo", 100, 20,
         "От 100 до 200 сом — зависит от рисунка", "From 100 to 200 KGS — depends on the design"),
    ]),
    ("Комплексные услуги", "Combo services", 30, [
        ("Друг + друг", "Friend + friend", 900, 80, "Стрижка для двоих", "Haircut for two"),
        ("Папа + сын", "Father + son", 700, 70, "Стрижка для двоих", "Haircut for two"),
        ("Стрижка + борода", "Haircut + beard", 800, 60, "", ""),
        ("Стрижка + чистка лица", "Haircut + facial cleansing", 900, 70, "", ""),
        ("Стрижка + камуфляж", "Haircut + grey camouflage", 900, 70, "", ""),
        ("Стрижка + королевское бритьё", "Haircut + royal shave", 900, 70, "", ""),
    ]),
]

# Без мастера онлайн-запись не работает: слоты считаются по графику мастера.
# Заводим одного, владелец переименует и добавит своих в кабинете.
DEFAULT_BARBER = "Свободный мастер"
DEFAULT_HOURS = ("10:00", "21:00")


class Command(BaseCommand):
    help = "Заводит барбершоп «Barber House» (Ош) с прайсом"

    def add_arguments(self, parser):
        parser.add_argument("--owner", help="username — выдать доступ в кабинет")
        parser.add_argument("--dry-run", action="store_true", help="ничего не писать в базу")

    @transaction.atomic
    def handle(self, *args, **opts):
        shop, created = Barbershop.objects.update_or_create(slug=SLUG, defaults=SHOP)
        self.stdout.write(self.style.SUCCESS(
            f"{'Создан' if created else 'Обновлён'} барбершоп #{shop.id} «{shop.name}» → /barbershop/{SLUG}/"
        ))

        total = 0
        for cat_name, cat_en, cat_order, services in CATALOG:
            cat, _ = ServiceCategory.objects.update_or_create(
                barbershop=shop, name=cat_name,
                defaults={"name_en": cat_en, "sort_order": cat_order, "is_active": True},
            )
            self.stdout.write(f"\n  {cat_name}")
            for i, (name, name_en, price, minutes, desc, desc_en) in enumerate(services, 1):
                svc, svc_created = Service.objects.update_or_create(
                    barbershop=shop, name=name,
                    defaults={
                        "category": cat, "name_en": name_en,
                        "description": desc, "description_en": desc_en,
                        "price": price, "duration_min": minutes,
                        "is_active": True, "sort_order": cat_order + i,
                    },
                )
                total += 1
                mark = "+" if svc_created else "·"
                note = f"  ({desc})" if desc else ""
                self.stdout.write(f"    {mark} {name} — {price} сом, {minutes} мин{note}")

        # Мастер по умолчанию + график на всю неделю
        barber, _ = Barber.objects.get_or_create(
            barbershop=shop, name=DEFAULT_BARBER,
            defaults={"experience": "", "is_active": True, "sort_order": 0},
        )
        for weekday in range(7):
            BarberSchedule.objects.update_or_create(
                barber=barber, weekday=weekday,
                defaults={"start_time": DEFAULT_HOURS[0], "end_time": DEFAULT_HOURS[1],
                          "is_working": True},
            )
        for svc in shop.services.all():
            BarberService.objects.get_or_create(barber=barber, service=svc)
        self.stdout.write(self.style.SUCCESS(
            f"\n  Мастер «{barber.name}»: график Пн–Вс {DEFAULT_HOURS[0]}–{DEFAULT_HOURS[1]}, "
            f"услуг — {total}"
        ))

        if opts["owner"]:
            User = get_user_model()
            user = User.objects.filter(username=opts["owner"]).first()
            if not user:
                self.stdout.write(self.style.ERROR(f"  Пользователь «{opts['owner']}» не найден"))
            else:
                BarbershopMembership.objects.get_or_create(user=user, barbershop=shop)
                self.stdout.write(self.style.SUCCESS(f"  Доступ в кабинет выдан: {user.username}"))

        self.stdout.write(self.style.SUCCESS(f"\nГотово: услуг — {total}, категорий — {len(CATALOG)}"))

        if opts["dry_run"]:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("--dry-run: изменения откачены"))
