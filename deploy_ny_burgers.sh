#!/bin/bash
# Собирает пакет для выкатки NY Burgers на прод и печатает команды заливки.
# Запускать ЛОКАЛЬНО из папки проекта:
#     bash deploy_ny_burgers.sh
#
# Ничего никуда не отправляет сам — только готовит архив.

set -euo pipefail
cd "$(dirname "$0")"

SERVER="root@69.10.50.176"
REMOTE="/var/www/mugivara"
PKG="ny_burgers_deploy.tar.gz"

# ── что везём ──────────────────────────────────────────────────────────────
FILES=(
  # код: поле темы у филиала, метка у позиции, выбор шаблона меню,
  # сохранение прозрачности у фото
  core/models.py
  core/migrations/0035_branch_template_slug.py
  catalog/models.py
  catalog/migrations/0019_branchitem_label.py
  public_site/views.py
  dashboard/views.py
  templates/dashboard/branch_edit.html
  templates/dashboard/item_edit.html

  # тема оформления: шаблон + статика (css, js, фото блюд и слои бургера)
  templates/custom/ny-burgers/menu.html
  static/custom/ny-burgers

  # данные и импорт
  ny_burgers_menu_data.py
  import_ny_burgers.py
  setup_ny_burgers.sh

  # переводы интерфейса темы
  locale/ky/LC_MESSAGES/django.po
  locale/ky/LC_MESSAGES/django.mo
  locale/en/LC_MESSAGES/django.po
  locale/en/LC_MESSAGES/django.mo
)

echo "Проверяю файлы…"
MISSING=0
for f in "${FILES[@]}"; do
  if [ ! -e "$f" ]; then echo "  НЕТ: $f"; MISSING=1; fi
done
[ "$MISSING" = "1" ] && { echo "Не хватает файлов — выкатка отменена."; exit 1; }
echo "  все на месте: ${#FILES[@]}"

echo "Собираю ${PKG} …"
COPYFILE_DISABLE=1 tar -czf "$PKG" --exclude='.DS_Store' --exclude='__pycache__' "${FILES[@]}"
SIZE=$(du -h "$PKG" | cut -f1)

cat <<EOF

Готово: $PKG ($SIZE)

Дальше выполните две команды (пароль сервера спросит сам):

  scp $PKG $SERVER:$REMOTE/
  ssh $SERVER "cd $REMOTE && tar -xzf $PKG && bash setup_ny_burgers.sh"

Скрипт на сервере сам применит миграции, соберёт статику,
создаст два филиала с меню и перезапустит gunicorn.

Чтобы задать свои названия филиалов:

  ssh $SERVER "cd $REMOTE && bash setup_ny_burgers.sh --branches 'Ош — Центр|Ош — Кулатова'"
EOF
