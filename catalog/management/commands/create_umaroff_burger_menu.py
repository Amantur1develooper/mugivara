"""
Создаёт ресторан «Umaroff Burger» + филиал + полное меню (RU/KY/EN), собранное
с реального PDF-меню заведения (20 страниц, бургеры/хот-доги/шаурма/пицца/суши/
куриные баскеты/комбо-наборы).

Фото блюд — кадры, вырезанные напрямую из фотографий на страницах самого PDF-меню
(реальная предметная съёмка блюд заведения), лежат рядом с этой командой в папке
_umaroff_burger_menu_photos/ — интернет при запуске не нужен.

Позиции «Стрипсы»/«Крылья» с двумя объёмами (5 шт / 7 шт) и «Умаров ассорти»
(на 2 / на 4 персоны) заведены как отдельные позиции меню с одним и тем же фото.

Использование:
    python manage.py create_umaroff_burger_menu
    python manage.py create_umaroff_burger_menu --slug "umaroff-burger-osh" --address "г. Ош, ..." --phone "+996700000000"
    python manage.py create_umaroff_burger_menu --dry-run
"""

import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "_umaroff_burger_menu_photos")

_RU_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify_ru(text: str) -> str:
    """slugify() кириллицу просто выбрасывает и даёт пустую строку — транслитерируем сами."""
    lowered = text.lower()
    transliterated = "".join(_RU_TO_LAT.get(ch, ch) for ch in lowered)
    return slugify(transliterated)


# ── Меню: (категория_ru, категория_ky, категория_en, [items]) ──────────────
# item = (name_ru, name_ky, name_en, price, desc_ru, desc_ky, desc_en, photo_key)
MENU_DATA = [
    ("Мясные тарелки", "Эт тарелкалары", "Meat Platters", [
        ("Умаров ассорти (2 персоны)", "Умаров эт ассортиси (2 адамга)", "Umarov Assorti (2 servings)", 550,
         "Гриль на курице, колбасках и мясных котлетах — сочный микс. Подаётся с деревенским картофелем и мягкой булочкой.",
         "Грильде бышырылган тоок эти, колбасалар жана эт отбивнойлорунун ширелүү микси. Айылдык картошка жана жумшак булочка менен берилет.",
         "Grilled chicken, sausages and meat cutlets — a juicy mix. Served with country-style potatoes and a soft bun.",
         "umarov-assorti.jpg"),
        ("Умаров ассорти (4 персоны)", "Умаров эт ассортиси (4 адамга)", "Umarov Assorti (4 servings)", 1100,
         "Гриль на курице, колбасках и мясных котлетах — сочный микс. Подаётся с деревенским картофелем и мягкой булочкой.",
         "Грильде бышырылган тоок эти, колбасалар жана эт отбивнойлорунун ширелүү микси. Айылдык картошка жана жумшак булочка менен берилет.",
         "Grilled chicken, sausages and meat cutlets — a juicy mix. Served with country-style potatoes and a soft bun.",
         "umarov-assorti.jpg"),
        ("Уч котлета", "Үч котлета", "Three Cutlets", 600,
         "Три сочные мясные котлеты на гриле, подаются с картофелем и маринованными огурцами.",
         "Грильде бышырылган үч даана эт котлети, картошка жана туздалган бадыраң менен берилет.",
         "Three juicy grilled meat cutlets, served with potatoes and pickles.",
         "uch-kotleta.jpg"),
    ]),
    ("Салаты", "Салаттар", "Salads", [
        ("Греческий салат", "Грек салаты", "Greek Salad", 280,
         "Помидоры, огурцы, болгарский перец, оливковое масло, сыр, оливки, красный лук, айсберг.",
         "Помидорлор, бадыраң, болгар калемпири, зайтун майы, сыр, зайтун, кызыл пияз, айсберг салаты.",
         "Tomatoes, cucumber, bell pepper, olive oil, cheese, olives, red onion, iceberg lettuce.",
         "grek-salaty.jpg"),
        ("Острый салат «Ачуу»", "Ачуу (өткүр) салат", "Spicy Salad", 280,
         "Говядина, помидоры, огурцы, лук, зелень, соевый соус.",
         "Уй эти, помидорлор, бадыраң, пияз, көк чөп, соя соусу.",
         "Beef, tomatoes, cucumber, onion, herbs, soy sauce.",
         "achuu-ostry.jpg"),
        ("Салат «Каприз дам»", "Айымдардын капризи", "Ladies' Caprice Salad", 300,
         "Куриное филе, сыр, свежий огурец, соломка из картофеля, фирменный соус.",
         "Тоок филеси, сыр, жаңы бадыраң, жүгөрү, пай картошкасы, фирмалык соус.",
         "Chicken fillet, cheese, fresh cucumber, potato straws, signature sauce.",
         "aiymdardyn-kaprizi.jpg"),
        ("Салат «Умаров»", "Умаров салаты", "Umarov Salad", 300,
         "Говядина, куриное филе, зелень, болгарский перец, кукуруза, огурец, опята, соевый соус.",
         "Уй эти, тоок филеси, көк чөп, калемпир, жүгөрү, бадыраң, козу карындар (опята), грибдер, соя соусу.",
         "Beef, chicken fillet, herbs, bell pepper, corn, cucumber, honey mushrooms, soy sauce.",
         "umarov-salaty.jpg"),
        ("Цезарь с курицей", "Тоок эти менен Цезарь", "Chicken Caesar Salad", 280,
         "Пекинская капуста, куриное филе, соус Цезарь, сыр, помидоры черри, сухарики.",
         "Пекин капустасы, тоок филеси, Цезарь соусу, сыр, черри помидоры, кептирилген нан.",
         "Chinese cabbage, chicken fillet, Caesar dressing, cheese, cherry tomatoes, croutons.",
         "tsezar-took.jpg"),
        ("Салат с хрустящим баклажаном", "Кытырак баклажан салаты", "Crispy Eggplant Salad", 250,
         "Хрустящий баклажан, помидоры черри, зелень, кунжут, фирменный соус.",
         "Кытырак баклажан, черри помидор, көк чөп, кунжут, фирмалык соус.",
         "Crispy eggplant, cherry tomatoes, herbs, sesame, signature sauce.",
         "kytyrak-baklazhan.jpg"),
    ]),
    ("Бургеры", "Бургерлер", "Burgers", [
        ("Умаров бургер", "Умаров бургер", "Umarov Burger", 280,
         "Булочка, солёный огурец, айсберг, помидор, соус барбекю, лук, говяжья котлета, два сыра, соусы.",
         "Булочка, туздалган бадыраң, айсберг салаты, помидор, барбекю соусу, пияз, уй этинен котлет, эки сыр, соустар.",
         "Bun, pickles, iceberg lettuce, tomato, BBQ sauce, onion, beef patty, two cheeses, sauces.",
         "umarov-burger.jpg"),
        ("Умаров чиз", "Умаров чиз", "Umarov Cheese", 300,
         "Булочка, солёный огурец, айсберг, помидоры, соус барбекю, лук, говяжья котлета, два сыра, соус.",
         "Булочка, туздалган бадыраң, айсберг салаты, помидорлор, барбекю соусу, пияз, уй этинен котлет, эки сыр, соус.",
         "Bun, pickles, iceberg lettuce, tomatoes, BBQ sauce, onion, beef patty, two cheeses, sauce.",
         "umarov-chiz.jpg"),
        ("Аралаш бургер", "Аралаш бургер", "Mixed Burger", 309,
         "Булочка, айсберг, помидор, соус барбекю, курица, говяжья котлета, два сыра, соус.",
         "Булочка, айсберг салаты, помидор, барбекю соусу, чикен (тоок эти), уй этинен котлет, эки сыр, соус.",
         "Bun, iceberg lettuce, tomato, BBQ sauce, chicken, beef patty, two cheeses, sauce.",
         "aralash-burger.jpg"),
        ("Фрешер бургер", "Фрешер бургер", "Fresher Burger", 300,
         "Булочка, два сыра, соус, айсберг, лук, соус барбекю, шампиньоны, говяжья котлета.",
         "Булочка, эки сыр, соус, айсберг салаты, пияз, барбекю соусу, шампиньондор, уй этинен котлет.",
         "Bun, two cheeses, sauce, iceberg lettuce, onion, BBQ sauce, mushrooms, beef patty.",
         "fresher-burger.jpg"),
        ("Вейл бургер", "Вейл бургер", "Veil Burger", 359,
         "Булочка, солёный огурец, айсберг, сыр, соус «Даблер», лук, двойная говяжья котлета.",
         "Булочка, туздалган бадыраң, айсберг салаты, сыр, Даблер соусу, пияз, уй этинен котлеттер.",
         "Bun, pickles, iceberg lettuce, cheese, Dabler sauce, onion, double beef patty.",
         "veil-burger.jpg"),
        ("Жемиштуу бургер", "Жемиштүү бургер", "Fruit Burger", 309,
         "Булочка, ананас, говяжья котлета, красный лук, капуста айсберг, два соуса.",
         "Булочка, ананас, уй этинен котлет, кызыл пияз, айсберг капустасы, 2 түрдүү соус.",
         "Bun, pineapple, beef patty, red onion, iceberg cabbage, two sauces.",
         "zhemishtuu-burger.jpg"),
        ("Зингер бургер", "Зингер бургер", "Zinger Burger", 300,
         "Булочка, майонез, айсберг, помидор, соус барбекю, халапеньо, говяжья котлета, два сыра, соус.",
         "Булочка, майонез, айсберг салаты, помидор, барбекю соусу, халапеньо, уй этинен котлет, эки сыр, соус.",
         "Bun, mayo, iceberg lettuce, tomato, BBQ sauce, jalapeño, beef patty, two cheeses, sauce.",
         "zinger-burger.jpg"),
        ("Стейк бургер", "Стейк бургер", "Steak Burger", 349,
         "Булочка, майонез, айсберг, огурец, стейк, сыр, соус барбекю, говяжья котлета.",
         "Булочка, майонез, айсберг салаты, бадыраң, стейк, сыр, барбекю соусу, уй этинен котлет.",
         "Bun, mayo, iceberg lettuce, cucumber, steak, cheese, BBQ sauce, beef patty.",
         "steik-burger.jpg"),
        ("Дабл бургер", "Дабл бургер", "Double Burger", 349,
         "Булочка, солёный огурец, айсберг, помидоры, соус барбекю, лук, говяжья котлета, два сыра, соус.",
         "Булочка, туздалган бадыраң, айсберг салаты, помидорлор, барбекю соусу, пияз, уй этинен котлет, эки сыр, соус.",
         "Bun, pickles, iceberg lettuce, tomatoes, BBQ sauce, onion, beef patty, two cheeses, sauce.",
         "dabl-burger.jpg"),
        ("Дабл чиз бургер", "Дабл чиз бургер", "Double Cheese Burger", 369,
         "Булочка, солёный огурец, айсберг, помидор, соус барбекю, лук, говяжья котлета, два сыра, соус, чеддер.",
         "Булочка, туздалган бадыраң, айсберг салаты, помидор, барбекю соусу, пияз, уй этинен котлет, эки сыр, соус, чеддер.",
         "Bun, pickles, iceberg lettuce, tomato, BBQ sauce, onion, beef patty, two cheeses, sauce, cheddar.",
         "dabl-chiz-burger.jpg"),
        ("Гамбургер с говядиной", "Уй эти гамбургер", "Beef Hamburger", 220,
         "Булочка, майонез, айсберг, огурец, стейк, сыр, соус барбекю.",
         "Булочка, майонез, айсберг салаты, бадыраң, стейк, сыр, барбекю соусу.",
         "Bun, mayo, iceberg lettuce, cucumber, steak, cheese, BBQ sauce.",
         "uy-eti-gamburger.jpg"),
        ("Цезарь бургер", "Цезар бургер", "Caesar Burger", 280,
         "Булочка, соус Цезарь, айсберг, лук, двойная говяжья котлета.",
         "Булочка, Цезарь соусу, айсберг салаты, пияз, уй этинен котлеттер.",
         "Bun, Caesar sauce, iceberg lettuce, onion, double beef patty.",
         "tsezar-burger.jpg"),
        ("Гамбургер с курицей", "Тавыкътан гамбургер", "Chicken Hamburger", 200,
         "Булочка, майонез, айсберг, огурец, стейк, сыр, соус барбекю, куриная котлета.",
         "Булочка, майонез, айсберг салаты, хыяр, стейк, сыр, барбекю соусы, тоок этинен котлет.",
         "Bun, mayo, iceberg lettuce, cucumber, steak, cheese, BBQ sauce, chicken patty.",
         "tavykytan-gamburger.jpg"),
        ("Сет бургер", "Сет бургер", "Set Burger", 380,
         "Куриные котлеты, говяжьи котлеты, опята, соус барбекю, сырный соус и картофель фри.",
         "Тоок этинен котлеттер, уй этинен котлеттер, козу карындар, барбекю соусу, сыр соусу жана картошка фри.",
         "Chicken patties, beef patties, honey mushrooms, BBQ sauce, cheese sauce and French fries.",
         "set-burger.jpg"),
        ("Чиккен чиз", "Чиккен чиз", "Chicken Cheese", 270,
         "Булочка, майонез, айсберг, помидор, соус барбекю, курица, сыр.",
         "Булочка, майонез, айсберг салаты, помидор, барбекю соусу, тоок эти, сыр.",
         "Bun, mayo, iceberg lettuce, tomato, BBQ sauce, chicken, cheese.",
         "chikken-chiz.jpg"),
        ("Чик бургер", "Чик бургер", "Chick Burger", 200,
         "Булочка, айсберг, помидор, соус Цезарь, куриные стрипсы.",
         "Булочка, айсберг салаты, помидор, Цезарь соусу, стрипстер.",
         "Bun, iceberg lettuce, tomato, Caesar sauce, chicken strips.",
         "chik-burger.jpg"),
        ("Чик-чиз бургер", "Чик-чиз бургер", "Chick Cheese Burger", 210,
         "Булочка, айсберг, помидор, соус Цезарь, куриные стрипсы, сыр.",
         "Булочка, айсберг салаты, помидор, Цезарь соусу, стрипстер, сыр.",
         "Bun, iceberg lettuce, tomato, Caesar sauce, chicken strips, cheese.",
         "chik-chiz-burger.jpg"),
    ]),
    ("Хот-доги", "Хот-догдор", "Hot Dogs", [
        ("Донер ассорти", "Донер ассорти", "Doner Assorti", 270,
         "Донер-мясо, жареная сосиска, помидоры, огурцы, красный лук, салат, фирменные соусы, булочка.",
         "Донер эти, куурулган сосиска, томаттар, бадырандар, кызыл пияз, салат, фирмалык соустар, булочка.",
         "Doner meat, fried sausage, tomatoes, cucumbers, red onion, lettuce, signature sauces, bun.",
         "doner-assorti.jpg"),
        ("Сырный хот-дог", "Сырдуу хот-дог", "Cheese Hot Dog", 200,
         "Сыр, кетчуп Heinz, горчица, сосиска, лук, солёный огурец, два сырных соуса, булочка.",
         "Сыр, Хайнц кетчубу, горчица, сосиска, пияз, туздалган бадыраң, эки сыр соусу, булочка.",
         "Cheese, Heinz ketchup, mustard, sausage, onion, pickle, two cheese sauces, bun.",
         "syrduu-hotdog.jpg"),
        ("Острый хот-дог", "Ачуу хот-дог", "Spicy Hot Dog", 210,
         "Халапеньо, кетчуп Heinz, горчица, сосиска, лук, солёный огурец, два сырных соуса, булочка.",
         "Халапеньо, Хайнц кетчубу, горчица, сосиска, пияз, туздалган бадыраң, эки сыр соусу, булочка.",
         "Jalapeño, Heinz ketchup, mustard, sausage, onion, pickle, two cheese sauces, bun.",
         "achuu-hotdog.jpg"),
        ("Фрешер хот-дог", "Фрешер хот-дог", "Fresher Hot Dog", 210,
         "Шампиньоны, кетчуп Heinz, горчица, сосиска, лук, солёный огурец, два сырных соуса, булочка.",
         "Шампиньондор, Хайнц кетчубу, горчица, сосиска, пияз, туздалган бадыраң, эки сыр соусу, булочка.",
         "Mushrooms, Heinz ketchup, mustard, sausage, onion, pickle, two cheese sauces, bun.",
         "fresher-hotdog.jpg"),
        ("Донер бургер", "Донер бургер", "Doner Burger", 250,
         "Донер-мясо, красный лук, свежий салат, томат и белые соусы, пшеничная булочка.",
         "Донер эти, кызыл пияз, жаңы салат, томат жана ак соустар, буудай булочкасы.",
         "Doner meat, red onion, fresh lettuce, tomato and white sauces, wheat bun.",
         "doner-burger.jpg"),
    ]),
    ("Шаурма и сэндвичи", "Шаурма жана сэндвичтер", "Shawarma & Sandwiches", [
        ("Шаурма ассорти", "Шаурмалар ассорти", "Shawarma Assorti", 309,
         "Говядина, курица, сосиска, огурец, помидоры, чесночный соус.",
         "Уй эти, тоок эти, сосиска, бадыраң, помидорлор, сарымсак соусу.",
         "Beef, chicken, sausage, cucumber, tomatoes, garlic sauce.",
         "shaurmalar-assorti.jpg"),
        ("Шаурма с говядиной", "Уй этинен шаурмалар", "Beef Shawarma", 280,
         "Лаваш, говядина, помидоры, огурцы, соус.",
         "Лаваш, уй эти, помидорлор, бадыраң, соус.",
         "Flatbread, beef, tomatoes, cucumbers, sauce.",
         "uy-eti-shaurma.jpg"),
        ("Шаурма с курицей", "Тоок этинен шаурмалар", "Chicken Shawarma", 260,
         "Лаваш, курица, помидоры, огурцы, соус.",
         "Лаваш, тоок эти, помидорлор, бадыраң, соус.",
         "Flatbread, chicken, tomatoes, cucumbers, sauce.",
         "took-eti-shaurma.jpg"),
        ("Клаб-сэндвич с картофелем фри", "Клаб сэндвич фри", "Club Sandwich with Fries", 250,
         "Тостовый хлеб, соус Цезарь, курица, айсберг, солёный огурец, картофель фри.",
         "Тостер наны, Цезарь соусу, чикен (тоок эти), айсберг салаты, туздалган бадыраң, картошка фри.",
         "Toast bread, Caesar sauce, chicken, iceberg lettuce, pickle, French fries.",
         "klab-sendvich-fri.jpg"),
        ("Чик лонгер", "Чик лонгер", "Chick Longer", 200,
         "Булочка, айсберг, помидор, соус Цезарь, куриные стрипсы.",
         "Булочка, айсберг салаты, помидор, Цезарь соусу, стрипстер.",
         "Bun, iceberg lettuce, tomato, Caesar sauce, chicken strips.",
         "chik-longer.jpg"),
    ]),
    ("Роллы в лаваше", "Лаваш роллдор", "Wrap Rolls", [
        ("Ролл с курицей", "Тоок этинен ролл", "Chicken Roll", 270,
         "Соус барбекю, сыр, курица, помидоры, айсберг, два сырных соуса, ролл из лаваша.",
         "Барбекю соусу, сыр, чикен (тоок эти), помидорлор, айсберг салаты, эки сыр соусу, ролл камыры.",
         "BBQ sauce, cheese, chicken, tomatoes, iceberg lettuce, two cheese sauces, flatbread roll.",
         "took-etinen-roll.jpg"),
        ("Ролл с говядиной", "Уй этинен ролл", "Beef Roll", 280,
         "Соус барбекю, говяжья котлета, помидоры, солёный огурец, лук, айсберг, два сырных соуса, ролл из лаваша.",
         "Барбекю соусу, уй этинен котлет, помидорлор, туздалган бадыраң, пияз, айсберг салаты, эки сыр соусу, ролл камыры.",
         "BBQ sauce, beef patty, tomatoes, pickle, onion, iceberg lettuce, two cheese sauces, flatbread roll.",
         "uy-etinen-roll.jpg"),
        ("Сырный ролл", "Сырдуу ролл", "Cheese Roll", 300,
         "Соус барбекю, сыр, говяжья котлета, помидоры, айсберг, два сырных соуса, ролл из лаваша.",
         "Барбекю соусу, сыр, уй этинен котлет, помидорлор, айсберг салаты, эки сыр соусу, ролл камыры.",
         "BBQ sauce, cheese, beef patty, tomatoes, iceberg lettuce, two cheese sauces, flatbread roll.",
         "syrduu-roll.jpg"),
    ]),
    ("Пицца", "Пицца", "Pizza", [
        ("Мясная пицца", "Эттуу пицца", "Meat Pizza", 600,
         "Тесто, моцарелла, соус для пиццы, красный лук, говядина, оливки. 34 см.",
         "Камыр, моцарелла сыры, пицца соусу, кызыл пияз, уй эти, зайтун.",
         "Dough, mozzarella, pizza sauce, red onion, beef, olives. 34 cm.",
         "ettuu-pizza.jpg"),
        ("Мясное ассорти пицца", "Эттуу аралаш пицца", "Mixed Meat Pizza", 560,
         "Тесто, моцарелла, соус для пиццы, красный лук, колбаса, курица, говядина, болгарский перец, солёный огурец. 34 см.",
         "Камыр, моцарелла сыры, пицца соусу, кызыл пияз, колбаса, тоок эти, уй эти, болгар калемпири, туздалган бадыраң.",
         "Dough, mozzarella, pizza sauce, red onion, sausage, chicken, beef, bell pepper, pickle. 34 cm.",
         "ettuu-aralash-pizza.jpg"),
        ("Пицца «Шаурма»", "Шаурма пиццасы", "Shawarma Pizza", 630,
         "Тесто, моцарелла, соус для пиццы, красный лук, говядина, солёный огурец, оливки. 34 см.",
         "Камыр, моцарелла сыры, пицца соусу, кызыл пияз, уй эти, туздалган бадыраң, зайтун.",
         "Dough, mozzarella, pizza sauce, red onion, beef, pickle, olives. 34 cm.",
         "shaurma-pizza.jpg"),
        ("Овощная пицца", "Жашылча пицца", "Vegetable Pizza", 550,
         "Тесто, моцарелла, соус для пиццы, курица, айсберг, огурец, чесночный соус, кетчуп, оливки. 34 см.",
         "Камыр, моцарелла сыры, пицца соусу, тоок эти, айсберг салаты, бадыраң, сарымсак соусу, кетчуп, зайтун.",
         "Dough, mozzarella, pizza sauce, chicken, iceberg lettuce, cucumber, garlic sauce, ketchup, olives. 34 cm.",
         "zhashylcha-pizza.jpg"),
        ("Пицца с ананасом", "Ананас менен пицца", "Pineapple Pizza", 530,
         "Тесто, ананас, сыр, копчёное куриное филе. 34 см.",
         "Камыр, ананас, сыр, ыштаган филе.",
         "Dough, pineapple, cheese, smoked chicken fillet. 34 cm.",
         "ananas-pizza.jpg"),
        ("Пицца «Барбекю»", "Барбекю пиццасы", "Barbecue Pizza", 630,
         "Тесто, моцарелла, соус для пиццы, помидоры, болгарский перец, говядина. 34 см.",
         "Камыр, моцарелла сыры, пицца соусу, помидорлор, болгар калемпири, уй эти.",
         "Dough, mozzarella, pizza sauce, tomatoes, bell pepper, beef. 34 cm.",
         "barbeku-pizza.jpg"),
        ("Пепперони", "Пепперони", "Pepperoni Pizza", 460,
         "Тесто, моцарелла, соус для пиццы, колбаса, оливки. 34 см.",
         "Камыр, моцарелла сыры, пицца соусу, колбаса, зайтун.",
         "Dough, mozzarella, pizza sauce, pepperoni sausage, olives. 34 cm.",
         "pepperoni-pizza.jpg"),
        ("Пицца «Донгусто»", "Донгусто пиццасы", "Dongusto Pizza", 630,
         "Тесто, моцарелла, соус для пиццы, красный лук, говядина, курица, паприка, оливки, шампиньоны. 34 см.",
         "Камыр, моцарелла сыры, пицца соусу, кызыл пияз, уй эти, тоок эти, паприка, зайтун, шампиньондор.",
         "Dough, mozzarella, pizza sauce, red onion, beef, chicken, paprika, olives, mushrooms. 34 cm.",
         "dongusto-pizza.jpg"),
        ("Куриная пицца", "Тоок эттуу пицца", "Chicken Pizza", 600,
         "Тесто, моцарелла, соус для пиццы, помидоры, куриное филе. 34 см.",
         "Камыр, моцарелла сыры, пицца соусу, помидорлор, тоок филеси.",
         "Dough, mozzarella, pizza sauce, tomatoes, chicken fillet. 34 cm.",
         "took-ettuu-pizza.jpg"),
        ("Пицца «Жюльен»", "Жюльен пиццасы", "Julienne Pizza", 460,
         "Куриное филе, шампиньоны, моцарелла, сливочный соус, кольца лука. 34 см.",
         "Тоок филеси, шампиньондор, моцарелла, каймак соусу, пияз шакекчелери.",
         "Chicken fillet, mushrooms, mozzarella, cream sauce, onion rings. 34 cm.",
         "zhulien-pizza.jpg"),
        ("Пицца «4 сезона»", "4 мезгил пицца", "Four Seasons Pizza", 550,
         "Тесто, моцарелла, соус для пиццы, курица, говядина, колбаса, помидоры. 34 см.",
         "Камыр, моцарелла сыры, пицца соусу, тоок эти, уй эти, колбаса, помидорлор.",
         "Dough, mozzarella, pizza sauce, chicken, beef, sausage, tomatoes. 34 cm.",
         "4-mezgil-pizza.jpg"),
        ("Маргарита", "Маргарита", "Margherita", 460,
         "Тесто, моцарелла, соус для пиццы, помидоры. 34 см.",
         "Камыр, моцарелла сыры, пицца соусу, помидорлор.",
         "Dough, mozzarella, pizza sauce, tomatoes. 34 cm.",
         "margarita-pizza.jpg"),
    ]),
    ("Суши-роллы", "Суши-роллдор", "Sushi Rolls", [
        ("Ролл «Америка»", "Ролл Америка", "Roll America", 420,
         "Копчёный лосось, угорь, сливочный сыр, хрустящий огурец, соус унаги, кунжут, рис, нори.",
         "Ышталган лосось, угорь, каймак сыры, кытырак бадыраң, унаги соусу, кунжут, күрүч, нори.",
         "Smoked salmon, eel, cream cheese, crispy cucumber, unagi sauce, sesame, rice, nori.",
         "roll-amerika.jpg"),
        ("Ролл «Бонито»", "Ролл Бонито", "Roll Bonito", 310,
         "Лосось, тунец, сливочный сыр, хрустящий огурец, хлопья бонито, рис, нори, манго-соус.",
         "Лосось, тунец, каймак сыры, кытырак бадыраң, бонито күкүмдөрү, күрүч, нори, манго соусу.",
         "Salmon, tuna, cream cheese, crispy cucumber, bonito flakes, rice, nori, mango sauce.",
         "roll-bonito.jpg"),
        ("Филадельфия", "Филадельфия", "Philadelphia", 380,
         "Лосось, сливочный сыр, хрустящий огурец, рис, нори.",
         "Лосось, каймак сыры, кытырак бадыраң, күрүч, нори.",
         "Salmon, cream cheese, crispy cucumber, rice, nori.",
         "filadelfiya.jpg"),
        ("Запечённый классический ролл", "Бышырылган классика роллу", "Baked Classic Roll", 380,
         "Лосось, сливочный сыр, огурец, фирменный запечённый соус.",
         "Лосось, каймак сыры, бадыраң, атайын бышырылган соус.",
         "Salmon, cream cheese, cucumber, signature baked sauce.",
         "byshyrylgan-klassika-rollu.jpg"),
        ("Фила Тобико", "Фила Тобико", "Fila Tobiko", 250,
         "Рис, нори, масаго, огурец, сыр, лосось.",
         "Күрүч, нори, масаго, бадыраң, сыр, лосось.",
         "Rice, nori, masago, cucumber, cheese, salmon.",
         "fila-tobiko.jpg"),
        ("Ролл «Токио»", "Ролл Токио", "Roll Tokyo", 350,
         "Лосось, окунь, сливочный сыр, сырный соус масаго, рис, нори.",
         "Лосось, окунь, каймак сыры, масаго менен сыр соусу, күрүч, нори.",
         "Salmon, perch, cream cheese, masago cheese sauce, rice, nori.",
         "roll-tokio.jpg"),
        ("Сырный ролл", "Сырдуу ролл", "Cheese Roll", 280,
         "Курица, сливочный сыр, пекинская капуста, сырный соус, сыр гауда, рис, нори.",
         "Тоок эти, каймак сыры, пекин капустасы, сыр соусу, гауда сыры, күрүч, нори.",
         "Chicken, cream cheese, Chinese cabbage, cheese sauce, gouda cheese, rice, nori.",
         "chiz-roll.jpg"),
        ("Чикен Унаги Саке", "Чикен Унаги Саке", "Chicken Unagi Sake", 410,
         "Рис, нори, сыр, укроп, паприка, угорь, курица, зелёный лук.",
         "Күрүч, нори, сыр, аскөк, паприка, угорь, тоок эти, жашыл пияз.",
         "Rice, nori, cheese, dill, paprika, eel, chicken, green onion.",
         "chiken-unagi-sake.jpg"),
        ("Ролл «Аяши»", "Ролл Аяши", "Roll Ayashi", 400,
         "Лосось в темпуре, сливочный сыр, сырный соус, масаго, рис, нори.",
         "Темпурадагы лосось, каймак сыры, сыр соусу, масаго, күрүч, нори.",
         "Tempura salmon, cream cheese, cheese sauce, masago, rice, nori.",
         "roll-ayashi.jpg"),
        ("Унаги Тунца", "Унаги Тунца", "Unagi Tuna", 420,
         "Угорь, сливочный сыр, тунец, фирменный соус, рис, нори, масаго, соус унаги, кунжут.",
         "Угорь, каймак сыры, тунец, фирмалык соус, күрүч, нори, масаго, унаги соусу, кунжут.",
         "Eel, cream cheese, tuna, signature sauce, rice, nori, masago, unagi sauce, sesame.",
         "unagi-tuntsa.jpg"),
        ("Унаги Саке", "Унаги Саке", "Unagi Sake", 410,
         "Лосось, угорь, томаго, сливочный сыр, нори, рис, соус унаги, кунжут.",
         "Лосось, угорь, томаго, каймак сыры, нори, күрүч, унаги соусу, кунжут.",
         "Salmon, eel, tamago, cream cheese, nori, rice, unagi sauce, sesame.",
         "unagi-sake.jpg"),
        ("Темпура Лосось", "Темпура Лосось", "Tempura Salmon", 320,
         "Лосось-гриль, сливочный сыр, пекинская капуста, масаго, нори, рис.",
         "Гриль лосось, каймак сыры, пекин капустасы, масаго, нори, күрүч.",
         "Grilled salmon, cream cheese, Chinese cabbage, masago, nori, rice.",
         "tempura-losos.jpg"),
    ]),
    ("Суши-сеты", "Суши топтомдору", "Sushi Sets", [
        ("Сет «Сахара»", "Сахара топтому", "Sahara Set", 1340,
         "37 кусочков запечённых роллов: запечённая курица, запечённый окунь, запечённый лосось, запечённый угорь; запечённые суши: 3 шт. с окунем, 2 шт. с курицей.",
         "37 кесек бышырылган роллдор: бышырылган тоок эти, бышырылган окунь, бышырылган лосось, бышырылган угорь; бышырылган суши: 3 даана окунь менен, 2 даана тоок эти менен.",
         "37 pieces of baked rolls: baked chicken, baked perch, baked salmon, baked eel; baked sushi: 3 pcs with perch, 2 pcs with chicken.",
         "sahara-toptomu.jpg"),
        ("Набор «Нагасаки»", "Нагасаки топтому", "Nagasaki Set", 910,
         "Набор запечённых роллов: с курицей, с угрём, с окунем.",
         "Бышырылган тоок роллу, бышырылган угорь, бышырылган окунь роллдорунун топтому.",
         "A set of baked rolls: with chicken, with eel, with perch.",
         "nabor-nagasaki.jpg"),
        ("Сет «Фудзияма»", "Фудзияма сет", "Fujiyama Set", 1220,
         "Набор классических роллов: Филадельфия, угорь, окунь и лосось.",
         "Классикалык Филадельфия, угорь, окунь жана лосось роллдорунун топтому.",
         "A set of classic rolls: Philadelphia, eel, perch and salmon.",
         "fudziyama-set.jpg"),
        ("Фирменный набор", "Фирмалык топтом", "Signature Set", 1010,
         "Лосось, угорь, окунь, масаго, сливочный сыр, салат из креветок, огурец, омлет, соус унаги, манго-соус.",
         "Лосось, угорь, окунь, масаго, каймак сыры, салат креветкасы, бадыраң, омлет, унаги соусу, манго соусу.",
         "Salmon, eel, perch, masago, cream cheese, shrimp salad, cucumber, omelet, unagi sauce, mango sauce.",
         "firmalyk-toptom.jpg"),
        ("Набор «Микс»", "Микс топтому", "Mix Set", 940,
         "Набор роллов из лосося, окуня, тунца и курицы.",
         "Лосось, окунь, тунец балыктары жана тоок эти менен жасалган роллдордун топтому.",
         "A set of rolls made with salmon, perch, tuna and chicken.",
         "nabor-miks.jpg"),
        ("Запечённый набор", "Бышырылган топтом", "Baked Set", 670,
         "Ролл с окунем, курицей, сливочным сыром и сырным соусом — 10 штук запечённых суши.",
         "Окунь балыгы менен ролл, тоок эти, каймак сыры жана сыр соусу менен 10 даана бышырылган суши.",
         "Perch roll, chicken, cream cheese and cheese sauce — 10 pieces of baked sushi.",
         "byshyrylgan-toptom.jpg"),
    ]),
    ("Куриные баскеты", "Тоок баскеттери", "Chicken Baskets", [
        ("Сулуу баскет", "Сулуу баскет", "Suluu Basket", 309,
         "4 стрипса, картофель фри, булочка, чесночный соус.",
         "4 даана стрипс, картошка фри, булочка, сарымсак соусу.",
         "4 chicken strips, French fries, bun, garlic sauce.",
         "suluu-basket.jpg"),
        ("Стрипсы (5 шт)", "Стрипстер (5 даана)", "Chicken Strips (5 pcs)", 240,
         "5 куриных стрипсов.",
         "5 даана куриный стрипс.",
         "5 chicken strips.",
         "stripsy.jpg"),
        ("Стрипсы (7 шт)", "Стрипстер (7 даана)", "Chicken Strips (7 pcs)", 316,
         "7 куриных стрипсов.",
         "7 даана куриный стрипс.",
         "7 chicken strips.",
         "stripsy.jpg"),
        ("Аралаш баскет", "Аралаш баскет", "Mixed Basket", 340,
         "3 крылышка, 2 стрипса, картофель фри, картофельные шарики, булочка, чесночный соус.",
         "3 даана канатча, 2 даана стрипс, картошка фри, картошка шарчалары, булочка, сарымсак соусу.",
         "3 chicken wings, 2 chicken strips, French fries, potato balls, bun, garlic sauce.",
         "aralash-basket.jpg"),
        ("Жылдыз баскет", "Жылдыз баскет", "Zhyldyz Basket", 289,
         "4 крылышка, картофель фри, булочка, чесночный соус.",
         "4 даана канатча, картошка фри, булочка, сарымсак соусу.",
         "4 chicken wings, French fries, bun, garlic sauce.",
         "zhyldyz-basket.jpg"),
        ("Крылья (5 шт)", "Канатча (5 даана)", "Chicken Wings (5 pcs)", 235,
         "5 куриных крылышек.",
         "5 даана тоок канатчасы.",
         "5 chicken wings.",
         "krylya.jpg"),
        ("Крылья (7 шт)", "Канатча (7 даана)", "Chicken Wings (7 pcs)", 329,
         "7 куриных крылышек.",
         "7 даана тоок канатчасы.",
         "7 chicken wings.",
         "krylya.jpg"),
    ]),
    ("Картофель и снеки", "Картошка жана снектер", "Fries & Sides", [
        ("Френч фри", "Френч фри", "French Fries", 150,
         "Картофель, нарезанный брусочками, обжаренный во фритюре.",
         "Брусок же пластинка түрүндө кесилген, фритюрда куурулган картошка.",
         "Potatoes cut into sticks, deep-fried.",
         "french-fri.jpg"),
        ("Деревенский картофель", "Айылдык картошка", "Country Potatoes", 170,
         "Картофель, обжаренный в масле с солью и специями.",
         "Айылдык картошка — майга куурулган, туз жана татымалдар менен татытылган картошка.",
         "Potatoes fried in oil with salt and spices.",
         "aiyldyk-kartoshka.jpg"),
        ("Корзина фри", "Фри корзинасы", "Fries Basket", 300,
         "Картофель фри крупной нарезки — хрустящая корочка и мягкая середина.",
         "Картошка фри — аппетиттүү кытырак кабыгы жана жумшак борбору бар чоң кесим картошка.",
         "Large-cut French fries — crispy on the outside, soft on the inside.",
         "fri-korzinasy.jpg"),
        ("Картофельные шарики", "Картошка шаарчалары", "Potato Balls", 170,
         "Нежные, вкусные и аппетитные картофельные шарики.",
         "Шарчалар назик, даамдуу жана абдан кооз болуп чыгат.",
         "Tender, tasty and appetizing potato balls.",
         "kartoshka-shaarchalary.jpg"),
    ]),
    ("Комбо-наборы", "Комбо топтомдор", "Combo Sets", [
        ("Комбо 2", "Комбо 2", "Combo 2", 900,
         "Три вида суши-роллов и напитки на компанию.",
         "Үч түрдүү суши-роллдор жана компанияга ичимдиктер.",
         "Three kinds of sushi rolls and drinks for a group.",
         "kombo-2.jpg"),
        ("Комбо 4", "Комбо 4", "Combo 4", 1600,
         "Пицца, картофель фри, суши-роллы и напитки.",
         "Пицца, картошка фри, суши-роллдор жана ичимдиктер.",
         "Pizza, French fries, sushi rolls and drinks.",
         "kombo-4.jpg"),
        ("Суши-сет 3", "Суши сеть 3", "Sushi Set 3", 1200,
         "Пять видов суши-роллов и напитки на компанию.",
         "Беш түрдүү суши-роллдор жана компанияга ичимдиктер.",
         "Five kinds of sushi rolls and drinks for a group.",
         "sushi-set-3.jpg"),
        ("Комбо 6", "Комбо 6", "Combo 6", 2600,
         "Две пиццы, куриные стрипсы, суши-роллы и напитки на большую компанию.",
         "Эки пицца, тоок стрипси, суши-роллдор жана чоң компанияга ичимдиктер.",
         "Two pizzas, chicken strips, sushi rolls and drinks for a big group.",
         "kombo-6.jpg"),
        ("Суши-сет 6", "Суши сеть 6", "Sushi Set 6", 2400,
         "Суши-роллы, бургеры, картофель фри и напитки на компанию.",
         "Суши-роллдор, бургерлер, картошка фри жана компанияга ичимдиктер.",
         "Sushi rolls, burgers, French fries and drinks for a group.",
         "sushi-set-6.jpg"),
    ]),
]


class Command(BaseCommand):
    help = "Создаёт ресторан «Umaroff Burger» + филиал + полное меню (RU/KY/EN) с фото"

    def add_arguments(self, parser):
        parser.add_argument("--name", default="Умаров Бургер", help="Название заведения (RU)")
        parser.add_argument("--slug", default="umaroff-burger", help="Slug ресторана")
        parser.add_argument("--name-ky", default="Умаров бургер", help="Название (KY), по умолчанию = RU")
        parser.add_argument("--name-en", default="Umaroff Burger", help="Название (EN)")
        parser.add_argument("--address", default="", help="Адрес филиала")
        parser.add_argument("--phone", default="+996 558 01 40 80", help="Телефон филиала")
        parser.add_argument("--no-photos", action="store_true", help="Не подставлять фото")
        parser.add_argument("--dry-run", action="store_true", help="Только показать, что будет создано, без записи в БД")

    def log(self, msg):
        self.stdout.write(msg)

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def err(self, msg):
        self.stdout.write(self.style.ERROR(msg))

    def handle(self, *args, **options):
        name_ru = options["name"].strip()
        slug = slugify_ru(options["slug"].strip()) or slugify_ru(name_ru)
        if not slug:
            raise CommandError("Не удалось сгенерировать slug — укажи его явно через --slug")
        name_ky = options["name_ky"].strip() or name_ru
        name_en = options["name_en"].strip() or name_ru
        address = options["address"].strip()
        phone = options["phone"].strip()
        no_photos = options["no_photos"]
        dry = options["dry_run"]

        total_items = sum(len(items) for *_, items in MENU_DATA)
        self.log(f"📋 Заведение : {name_ru} (slug={slug})")
        self.log(f"   Категорий : {len(MENU_DATA)}")
        self.log(f"   Позиций   : {total_items}")
        self.log(f"   Фото      : {'выключены (--no-photos)' if no_photos else PHOTOS_DIR}")

        if dry:
            for cat_ru, cat_ky, cat_en, items in MENU_DATA:
                self.log(f"\n📂 {cat_ru} / {cat_ky} / {cat_en} ({len(items)})")
                for name_r, name_k, name_e, price, *_rest, photo_key in items:
                    self.log(f"   • {name_r} — {price} сом  ({name_e} / {name_k})  [{photo_key}]")
            self.ok("\n✅ DRY RUN — в базу ничего не записано.")
            return

        from catalog.models import (
            BranchCategory, BranchCategoryItem, BranchItem,
            BranchMenuSet, Category, Item, ItemCategory, MenuSet,
        )
        from core.models import Branch, Restaurant

        if Restaurant.objects.filter(slug=slug).exists():
            raise CommandError(
                f"Ресторан со slug='{slug}' уже существует. "
                f"Выбери другой --slug или удали существующий вручную."
            )

        # Кэш байтов фото по имени файла, чтобы не читать с диска на каждую позицию
        photo_cache = {}

        def get_photo_content(photo_key):
            if no_photos or not photo_key:
                return None
            if photo_key not in photo_cache:
                path = os.path.join(PHOTOS_DIR, photo_key)
                if not os.path.exists(path):
                    self.err(f"   ⚠️ фото не найдено: {path}")
                    photo_cache[photo_key] = None
                else:
                    with open(path, "rb") as f:
                        photo_cache[photo_key] = f.read()
            return photo_cache[photo_key]

        restaurant = Restaurant.objects.create(
            slug=slug, name_ru=name_ru, name_ky=name_ky, name_en=name_en,
            is_active=True,
        )
        self.ok(f"✨ Создан ресторан id={restaurant.id} ({name_ru})")

        branch = Branch.objects.create(
            restaurant=restaurant,
            name_ru=name_ru, name_ky=name_ky, name_en=name_en,
            address=address, phone=phone,
            is_active=True,
        )
        self.ok(f"✨ Создан филиал id={branch.id}")

        menu_set = MenuSet.objects.create(
            restaurant=restaurant, name="Основное меню", is_active=True,
        )
        BranchMenuSet.objects.create(branch=branch, menu_set=menu_set)
        self.log(f"   MenuSet id={menu_set.id}")

        items_created = 0
        photos_set = 0
        for cat_idx, (cat_ru, cat_ky, cat_en, items) in enumerate(MENU_DATA):
            category = Category.objects.create(
                menu_set=menu_set, name_ru=cat_ru, name_ky=cat_ky, name_en=cat_en,
            )
            branch_category = BranchCategory.objects.create(
                branch=branch, category=category,
                sort_order=cat_idx, is_active=True,
            )
            self.log(f"\n📂 [{cat_idx + 1}/{len(MENU_DATA)}] {cat_ru} — {len(items)} поз.")

            for item_idx, (name_r, name_k, name_e, price, desc_r, desc_k, desc_e, photo_key) in enumerate(items):
                item = Item(
                    restaurant=restaurant,
                    name_ru=name_r, name_ky=name_k, name_en=name_e,
                    description_ru=desc_r, description_ky=desc_k, description_en=desc_e,
                    base_price=price,
                )
                content = get_photo_content(photo_key)
                photo_status = ""
                if content:
                    # прямое присваивание, а не .save(): иначе upload_to подставится
                    # дважды при повторном сохранении внутри Item.save()->_compress_photo()
                    item.photo = ContentFile(content, name=photo_key)
                    photos_set += 1
                    photo_status = " 📷"
                item.save()

                branch_item = BranchItem.objects.create(
                    branch=branch, item=item,
                    price=price, sort_order=item_idx, is_available=True,
                )
                ItemCategory.objects.create(item=item, category=category, sort_order=item_idx)
                BranchCategoryItem.objects.create(
                    branch_category=branch_category, branch_item=branch_item,
                    sort_order=item_idx,
                )
                items_created += 1
                self.log(f"   • {name_r} — {price} сом{photo_status}")

        self.stdout.write("")
        self.ok("=" * 55)
        self.ok("✅ Готово!")
        self.log(f"   Ресторан   : {name_ru} (id={restaurant.id}, slug={slug})")
        self.log(f"   Филиал     : id={branch.id}")
        self.log(f"   Категорий  : {len(MENU_DATA)}")
        self.log(f"   Позиций    : {items_created}")
        self.log(f"   С фото     : {photos_set}/{items_created}")
        self.log(f"   Меню       : http://<host>/ru/{branch.id}/menu/")
        self.ok("=" * 55)
        self.log("")
        self.log("📷 Фото — кадры, вырезанные напрямую из фотографий блюд в PDF-меню заведения.")
        self.log("")
        self.log("📌 Если нужно привязать аккаунт владельца к ресторану:")
        self.log("   python manage.py shell")
        self.log("   from core.models import Restaurant, Membership")
        self.log("   from django.contrib.auth.models import User")
        self.log("   u = User.objects.get(username='ЛОГИН_ВЛАДЕЛЬЦА')")
        self.log(f"   r = Restaurant.objects.get(slug='{slug}')")
        self.log("   Membership.objects.get_or_create(user=u, restaurant=r)")
