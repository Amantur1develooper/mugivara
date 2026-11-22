"""Создаёт клуб и первого администратора — чтобы начать работать.

    python manage.py fitness_club_add --name "Атлет Ош" --slug atlet-osh --user admin

Дальше всё настраивается в кабинете: секции, абонементы, тренеры, чаты.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from fitness.models import ClubStaff, FitnessClub


class Command(BaseCommand):
    help = "Создать фитнес-клуб и назначить администратора"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="название клуба")
        parser.add_argument("--slug", help="адрес на сайте; по умолчанию из названия")
        parser.add_argument("--user", required=True, help="логин администратора")
        parser.add_argument("--phone", default="", help="телефон")
        parser.add_argument("--address", default="", help="адрес")

    def handle(self, *args, **opts):
        User = get_user_model()
        user = User.objects.filter(username=opts["user"]).first()
        if not user:
            raise CommandError(f"Пользователя «{opts['user']}» нет. "
                               f"Создайте его или укажите существующий логин.")

        slug = (opts.get("slug") or slugify(opts["name"], allow_unicode=False)
                or slugify(opts["name"]))
        if not slug:
            raise CommandError("Не смог составить адрес — задайте --slug")
        if FitnessClub.objects.filter(slug=slug).exists():
            raise CommandError(f"Клуб с адресом «{slug}» уже есть")

        club = FitnessClub.objects.create(
            name=opts["name"], slug=slug,
            phone=opts.get("phone") or "", address=opts.get("address") or "",
        )
        ClubStaff.objects.create(user=user, club=club, role=ClubStaff.Role.ADMIN)

        self.stdout.write(self.style.SUCCESS(f"\nКлуб «{club.name}» создан."))
        self.stdout.write(f"  Кабинет:  /ru/cabinet/fitness/{club.id}/")
        self.stdout.write(f"  Сайт:     /ru/fitness/{club.slug}/")
        self.stdout.write(f"  Админ:    {user.username}")
        self.stdout.write("\nДальше в кабинете, раздел «Настройки»: секции, "
                          "абонементы, тренеры и два чата Telegram.")
