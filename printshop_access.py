# -*- coding: utf-8 -*-
"""Показывает, кто имеет доступ к полиграфическим центрам."""
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.contrib.auth import get_user_model
from printshop.models import PrintCenter, PrintMembership

print("ЦЕНТРЫ:")
for c in PrintCenter.objects.all().order_by("id"):
    who = list(PrintMembership.objects.filter(center=c)
               .values_list("user__username", "role"))
    print(f"  id={c.id:<4} {c.slug:<22} доступ: {who or 'НИ У КОГО'}")

print("\nСУПЕРПОЛЬЗОВАТЕЛИ (видят всё):")
for u in get_user_model().objects.filter(is_superuser=True):
    print("  ", u.username)


# Выдать доступ:  python printshop_access.py --grant ЛОГИН --center SLUG
import sys
if "--grant" in sys.argv:
    login = sys.argv[sys.argv.index("--grant") + 1]
    slug = sys.argv[sys.argv.index("--center") + 1]
    u = get_user_model().objects.filter(username=login).first()
    c = PrintCenter.objects.filter(slug=slug).first()
    if not u:
        sys.exit(f"нет пользователя «{login}»")
    if not c:
        sys.exit(f"нет центра «{slug}»")
    m, created = PrintMembership.objects.get_or_create(
        user=u, center=c, defaults={"role": PrintMembership.Role.OWNER})
    print(f"\n{'выдан' if created else 'уже был'} доступ: {login} → {c.name_ru} ({m.role})")
