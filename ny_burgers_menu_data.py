# -*- coding: utf-8 -*-
"""Меню NY Burgers Osh на трёх языках.

Источник: /Users/amanturerkinov/Desktop/ny-burgers-site (js/app.js, массив MENU).
Цены и описания взяты оттуда без изменений, переводы — ky/en.

photo — имя файла в папке img/ исходного сайта (webp с прозрачным фоном).
old_price — зачёркнутая цена (запускает бейдж promo_label).
"""

RESTAURANT = {
    "slug": "ny-burgers",
    "ru": "NY Burgers",
    "ky": "NY Burgers",
    "en": "NY Burgers",
    "about_ru": "Бургеры в стиле Нью-Йорка. Две говяжьи котлеты, тянущийся чеддер "
                "и бриошь с кунжутом. Каждый бургер собираем под заказ.",
    "instagram": "https://www.instagram.com/newyork.burgers.osh/",
}

# Филиалы. Названия и адреса — черновые: переименуйте в кабинете или передайте
# скрипту --branches "Название 1|Название 2". Меню у филиалов общее, цены свои.
BRANCHES = [
    {
        "ru": "NY Burgers — Ош, Центр",
        "ky": "NY Burgers — Ош, Борбор",
        "en": "NY Burgers — Osh, Downtown",
        "address": "Ош, Кыргызстан",
    },
    {
        "ru": "NY Burgers — Ош, второй филиал",
        "ky": "NY Burgers — Ош, экинчи филиал",
        "en": "NY Burgers — Osh, second location",
        "address": "Ош, Кыргызстан",
    },
]

# Совместимость со старым импортом (один филиал)
BRANCH = BRANCHES[0]

CATEGORIES = [
    {
        "slug": "burgers",
        "ru": "Бургеры", "ky": "Бургерлер", "en": "Burgers",
        "items": [
            {
                "ru": "Комбо Нью-Йорк", "ky": "«Нью-Йорк» комбосу", "en": "New York Combo",
                "d_ru": "Double Cheese, картофель фри, сырные палочки и халапеньо.",
                "d_ky": "Double Cheese, фри картошка, сыр таякчалары жана халапеньо.",
                "d_en": "Double Cheese, French fries, cheese sticks and jalapeños.",
                "price": 690, "old_price": 790, "promo_label": "Комбо",
                "photo": "tray.webp",
            },
            {
                "ru": "Double Cheese", "ky": "Double Cheese", "en": "Double Cheese",
                "d_ru": "Две говяжьи котлеты, двойной чеддер, огурцы, лук, помидор, "
                        "сырный, барбекю и фирменный соусы.",
                "d_ky": "Эки уй этинен котлет, кош чеддер, бадыраң, пияз, помидор, "
                        "сыр, барбекю жана фирмалык соустар.",
                "d_en": "Two beef patties, double cheddar, pickles, onion, tomato, "
                        "cheese, BBQ and signature sauces.",
                "price": 390, "photo": "double.webp",
            },
            {
                "ru": "New York Classic", "ky": "New York Classic", "en": "New York Classic",
                "d_ru": "Говяжья котлета, чеддер, томат, маринованные огурцы, BBQ и соус.",
                "d_ky": "Уй этинен котлет, чеддер, помидор, маринадталган бадыраң, BBQ жана соус.",
                "d_en": "Beef patty, cheddar, tomato, pickles, BBQ and sauce.",
                "price": 290, "photo": "classic.webp",
            },
            {
                "ru": "BBQ Cheeseburger", "ky": "BBQ Cheeseburger", "en": "BBQ Cheeseburger",
                "d_ru": "Говяжья котлета на гриле, чеддер, соус BBQ, фирменный соус.",
                "d_ky": "Грильде бышырылган уй эт котлети, чеддер, BBQ соусу, фирмалык соус.",
                "d_en": "Grilled beef patty, cheddar, BBQ sauce, signature sauce.",
                "price": 280, "photo": "bbq.webp",
            },
            {
                "ru": "Chicken BBQ", "ky": "Chicken BBQ", "en": "Chicken BBQ",
                "d_ru": "Хрустящие куриные стрипсы, чеддер, BBQ и сливочный соус.",
                "d_ky": "Кыткылдак тоок стрипстери, чеддер, BBQ жана каймак соусу.",
                "d_en": "Crispy chicken strips, cheddar, BBQ and creamy sauce.",
                "price": 270, "photo": "chicken.webp",
            },
        ],
    },
    {
        "slug": "sides",
        "ru": "Закуски", "ky": "Жеңил тамактар", "en": "Sides",
        "items": [
            {
                "ru": "Картофель фри", "ky": "Фри картошка", "en": "French Fries",
                "d_ru": "Толстая нарезка, хрустящая корочка, соль.",
                "d_ky": "Жоон кесилген, кыткылдак кабык, туз.",
                "d_en": "Thick cut, crispy crust, salt.",
                "price": 120, "photo": "fries.webp",
            },
            {
                "ru": "Картофель по-деревенски", "ky": "Айылча картошка", "en": "Potato Wedges",
                "d_ru": "Картофельные дольки со шкуркой и специями.",
                "d_ky": "Кабыгы менен кесилген картошка, татымалдар менен.",
                "d_en": "Skin-on potato wedges with spices.",
                "price": 140, "photo": "wedges.webp",
            },
            {
                "ru": "Сырные палочки", "ky": "Сыр таякчалары", "en": "Cheese Sticks",
                "d_ru": "Моцарелла в панировке, тянется как надо.",
                "d_ky": "Панировкадагы моцарелла, керектүүдөй созулат.",
                "d_en": "Breaded mozzarella, stretches just right.",
                "price": 220, "photo": "sticks.webp",
            },
            {
                "ru": "Наггетсы", "ky": "Наггетстер", "en": "Nuggets",
                "d_ru": "Куриное филе в хрустящей панировке, 6 шт.",
                "d_ky": "Кыткылдак панировкадагы тоок эти, 6 даана.",
                "d_en": "Chicken fillet in crispy breading, 6 pcs.",
                "price": 190, "photo": "nuggets.webp",
            },
            {
                "ru": "Халапеньо", "ky": "Халапеньо", "en": "Jalapeños",
                "d_ru": "Маринованный острый перец, добавка к бургеру.",
                "d_ky": "Маринадталган ачуу калемпир, бургерге кошумча.",
                "d_en": "Pickled hot peppers, burger add-on.",
                "price": 60, "photo": "jalapeno.webp",
            },
        ],
    },
]
