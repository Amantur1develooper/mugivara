"""
Django management command to import Dolce Vita Family restaurant menu.

Usage:
    python manage.py import_dolcevita
    python manage.py import_dolcevita --dry-run       # parse only, no DB writes
    python manage.py import_dolcevita --no-images     # skip image downloads
    python manage.py import_dolcevita --reset         # delete existing and reimport
"""

import os
from decimal import Decimal

from django.core.management.base import BaseCommand

# ─── Full menu data extracted from DOLCE MENU 2026.pdf ───────────────────────

RESTAURANT = {
    "name_ru": "Долче Вита Фамили",
    "name_ky": "Долче Вита Фамили",
    "name_en": "Dolce Vita Family",
    "slug": "dolce-vita-family",
    "about_ru": "Ресторан итальянской и международной кухни Dolce Vita Family. Обслуживание 15%.",
    "about_ky": "Итальян жана эл аралык ашкана Dolce Vita Family ресторану. Тейлөө 15%.",
    "about_en": "Dolce Vita Family - Italian and international cuisine restaurant. Service charge 15%.",
}

BRANCH = {
    "name_ru": "Долче Вита Фамили",
    "name_ky": "Долче Вита Фамили",
    "name_en": "Dolce Vita Family",
    "is_open_24h": False,
    "work_days": "0,1,2,3,4,5,6",
}

# Format: (name_ru, name_ky, name_en)
CATEGORIES = [
    ("Пицца", "Пиццалар", "Pizza"),
    ("Хлеб и Выпечка", "Нан жана Бышырыктар", "Bread & Pastries"),
    ("Завтраки", "Таңкы тамактар", "Breakfasts"),
    ("Салаты", "Салаттар", "Salads"),
    ("Закуски", "Закускалар", "Appetizers"),
    ("Супы", "Суюк тамактар", "Soups"),
    ("Паста", "Паста", "Pasta"),
    ("Горячие блюда", "Экинчи тамактар", "Hot Dishes"),
    ("Шашлыки по-азербайджански", "Азербайжан шишкебектери", "Azerbaijani Grills"),
    ("Стейки", "Стейктер", "Steaks"),
    ("Бургеры", "Бургерлер", "Burgers"),
    ("Роллы", "Роллдор", "Rolls"),
    ("Десерты", "Ширриндиктер", "Desserts"),
    ("Чаи", "Чайлар", "Teas"),
    ("Напитки", "Суусундуктар", "Drinks"),
    ("Смузи", "Смузи", "Smoothies"),
    ("Кофе", "Кофе", "Coffee"),
    ("Лимонады", "Лимонадтар", "Lemonades"),
    ("Коктейли", "Коктейлдер", "Cocktails"),
]

# Format: (category_index, name_ru, name_ky, name_en, desc_ru, desc_ky, desc_en, price, image_search_query)
# category_index refers to CATEGORIES list above (0-based)
ITEMS = [
    # ── ПИЦЦА (0) ──────────────────────────────────────────────────────────────
    (0, "Пицца с сыром Буррата", "Пицца Буррата Быштагы Менен", "Pizza with Burrata Cheese",
     "Тесто, сыр буррата, руккола, помидоры, соус песто",
     "Камыр, буррата быштагы, руккола, помидор, песто соусу",
     "Dough, burrata cheese, arugula, tomatoes, pesto sauce",
     540, "pizza burrata cheese arugula pesto"),

    (0, "Пицца Детская", "Балдардын Пиццасы", "Kids Pizza",
     "Тесто, колбаса салями, сосиски, картофель фри, сыр Моцарелла, итальянский томатный соус",
     "Камыр, салями колбасасы, ичке колбаса, картошке фри, Моцарелла быштагы, италиялык томат соусу",
     "Dough, salami sausage, sausages, french fries, mozzarella cheese, Italian tomato sauce",
     480, "kids pizza salami sausages french fries"),

    (0, "Пицца с Грушей и Сыром Горгонзола", "Пицца Алмурут Жана Горгонзола Быштагы Менен", "Pizza with Pear and Gorgonzola",
     "Тесто, сырный соус, моцарелла, сулугуни, горгонзола, пармезан, груша, греческий орех",
     "Камыр, быштак соусу, моцарелла, сулугуни, горгонзола, пармезан, алмурут, жаңгак",
     "Dough, cheese sauce, mozzarella, sulguni, gorgonzola, parmesan, pear, walnut",
     640, "pizza pear gorgonzola cheese walnut"),

    (0, "Пицца Филадельфия", "Филадельфия Пиццасы", "Philadelphia Pizza",
     "Тесто, сыр творожный, слабосоленая семга, вяленые помидоры, руккола",
     "Камыр, быштак, бир аз туздалган семга балыгы, сурсутулген помидор, руккола",
     "Dough, cream cheese, lightly salted salmon, sun-dried tomatoes, arugula",
     650, "pizza philadelphia salmon cream cheese sun-dried tomatoes"),

    (0, "Пицца с Соусом Песто", "Пицца Песто Соусу Менен", "Pesto Pizza",
     "Тесто, курица, сыр, помидоры черри, соус песто",
     "Камыр, тоок эти, быштак, черри помидору, песто соусу",
     "Dough, chicken, cheese, cherry tomatoes, pesto sauce",
     580, "pizza pesto chicken cherry tomatoes"),

    (0, "Пицца Маргарита", "Маргарита Пиццасы", "Margherita Pizza",
     "Тесто, сладкие помидоры, сыр Моцарелла, итальянский томатный соус",
     "Камыр, таттуу помидор, Моцарелла быштагы, италиялык томат соусу",
     "Dough, sweet tomatoes, mozzarella cheese, Italian tomato sauce",
     380, "pizza margherita classic tomato mozzarella basil"),

    (0, "Пицца со Страчателлой", "Пицца Страчателла Быштагы Менен", "Pizza with Stracciatella",
     "Тесто, сыр Страчателла, руккола, помидоры, оливковое масло",
     "Камыр, Страчателла быштагы, руккола, помидор, зайтун майы",
     "Dough, stracciatella cheese, arugula, tomatoes, olive oil",
     540, "pizza stracciatella arugula cherry tomatoes"),

    (0, "Пицца Дольче Вита", "Дольче Вита Пиццасы", "Dolce Vita Pizza",
     "Тесто, колбаса Салями, сосиски, индейка, копченая курица, оливки, маслины, шампиньоны, сыр Моцарелла, итальянский томатный соус",
     "Камыр, салями колбасасы, ичке колбаса, үндүк, ышталган тоок, зайтун, шампиньон козу карындары, Моцарелла быштагы, италиялык томат соусу",
     "Dough, salami, sausages, turkey, smoked chicken, olives, black olives, mushrooms, mozzarella cheese, Italian tomato sauce",
     590, "pizza meat lovers salami olives mushrooms"),

    (0, "Пицца Пепперони", "Пепперони Пиццасы", "Pepperoni Pizza",
     "Тесто, колбаса Салями, сыр Моцарелла, итальянский томатный соус",
     "Камыр, салями колбасасы, Моцарелла быштагы, италиялык томат соусу",
     "Dough, salami sausage, mozzarella cheese, Italian tomato sauce",
     560, "pizza pepperoni salami classic"),

    (0, "Пицца Мясная", "Эт Пиццасы", "Meat Pizza",
     "Тесто, нежная телячья вырезка, кабачки, перец болгарский, баклажаны, лук красный, сыр Моцарелла, итальянский томатный соус",
     "Камыр, жаш торпоктун эти, кабак, болгар калемпири, баклажан, кызыл пияз, Моцарелла быштагы, италиялык томат соусу",
     "Dough, tender veal fillet, zucchini, bell pepper, eggplant, red onion, mozzarella cheese, Italian tomato sauce",
     680, "pizza meat veal eggplant vegetables"),

    (0, "Пицца 4 Сыра", "4 Быштак Пиццасы", "Four Cheese Pizza",
     "Тесто, 4 сыра: Моцарелла, Дор-Блю, Сулугуни, Пармезан, фирменный сметанный соус",
     "Камыр, Моцарелла, Дор-Блю, Сулугуни, Пармезан быштактары, өзгөчө каймак соусу",
     "Dough, 4 cheeses: Mozzarella, Dor-Blu, Sulguni, Parmesan, signature sour cream sauce",
     580, "four cheese pizza quattro formaggi"),

    (0, "Пицца с Курицей", "Пицца Тоок Менен", "Chicken Pizza",
     "Тесто, курица копченая, курица отварная, сыр и пилати",
     "Камыр, ышталган тоок, кайнатылган тоок, быштак жана пилати",
     "Dough, smoked chicken, boiled chicken, cheese and pilati",
     480, "chicken pizza smoked grilled mozzarella"),

    (0, "Пицца Мексикано", "Мексикано Пиццасы", "Mexicano Pizza",
     "Тесто, фарш говяжий, сыр, лук красный, перец чили",
     "Камыр, майдаланган эт, быштак, кызыл пияз, чили калемпири",
     "Dough, ground beef, cheese, red onion, chili pepper",
     540, "pizza mexicano beef jalapeno spicy"),

    (0, "Хачапури по-Аджарски", "Аджария Хачапуриси", "Adjarian Khachapuri",
     "Тесто, сыр сулугуни, брынза, яйцо желток, сыр пармезан",
     "Камыр, сулугуни быштагы, брынза, жумурткалын сарысы, пармезан быштагы",
     "Dough, sulguni cheese, brynza, egg yolk, parmesan cheese",
     580, "khachapuri adjarian georgian bread egg cheese"),

    (0, "Хачапури Фирменный", "Өзгөчө Хачапури", "Signature Khachapuri",
     "Тесто, сыр сулугуни, брынза, яйцо, сыр пармезан",
     "Камыр, сулугуни быштагы, брынза, жумуртка, пармезан быштагы",
     "Dough, sulguni cheese, brynza, egg, parmesan cheese",
     590, "khachapuri cheese bread Georgia"),

    # ── ХЛЕБ И ВЫПЕЧКА (1) ─────────────────────────────────────────────────────
    (1, "Боорсок", "Боорсок", "Boorsok",
     "Боорсоки — традиционное кыргызское лакомство, небольшие жареные кусочки теста",
     "Боорсок — кыргыздын салттуу даамы, жарылган камырдын кичинекей бөлүктөрү",
     "Boorsok — traditional Kyrgyz treat, small fried dough pieces",
     220, "boorsok kyrgyz fried dough"),

    (1, "Хлебное Ассорти", "Нан Топтому", "Bread Assortment",
     "Кукурузный, злаковый, бородинский, чиабатта, хлеб с сухофруктами и орехами",
     "Жүгөрү, жарма, бородино, чиабатта италия наны, кургатылган жемиштер жана жаңгактар менен нан",
     "Corn, grain, Borodino, ciabatta, bread with dried fruits and nuts",
     180, "bread assortment basket sourdough ciabatta"),

    (1, "Бухарская Лепёшка", "Бухара Токочу", "Bukhara Flatbread",
     "Традиционная узбекская лепёшка",
     "Салттуу өзбек токочу",
     "Traditional Uzbek flatbread",
     50, "bukhara uzbek flatbread tandoor"),

    (1, "Фокачча", "Фокачча", "Focaccia",
     "Итальянская лепёшка (классическая / с розмарином / с сыром)",
     "Италиялык нан (классикалык / розмарин менен / сыр менен)",
     "Italian flatbread (classic / with rosemary / with cheese)",
     90, "focaccia italian bread olive oil rosemary"),

    (1, "Круассан", "Круассан", "Croissant",
     "Свежий круассан (классический / шоколадный / ванильный)",
     "Жаңы жасалган круассан (классикалык / шоколад / ваниль)",
     "Fresh croissant (classic / chocolate / vanilla)",
     140, "croissant fresh pastry buttery"),

    # ── ЗАВТРАКИ (2) ───────────────────────────────────────────────────────────
    (2, "Бельгийские Вафли", "Бельгия Вафлиси", "Belgian Waffles",
     "Бельгийские вафли, подаются с мороженым",
     "Бельгиялык вафли, бал муздак менен берилет",
     "Belgian waffles, served with ice cream",
     240, "belgian waffles ice cream caramel"),

    (2, "Каша Рисовая с Карамелью и Арахисом", "Карамель Жана Жержаңгак Кошулган Күрүч Боткосу", "Rice Porridge with Caramel and Peanuts",
     "Рис, молоко, сливки, карамель, арахис, гель из фиников",
     "Күрүч, сүт, каймак, карамель, жержаңгак, курма гели",
     "Rice, milk, cream, caramel, peanuts, date gel",
     220, "rice porridge caramel peanuts breakfast"),

    (2, "Каша Овсяно-Гречневая", "Сулу-Гречка Боткосу", "Oat-Buckwheat Porridge",
     "Овсяная крупа, гречневая крупа, молоко, гель из фиников, семена льна",
     "Сулу, гречка, сүт, курма гели, зыгыр уруктары",
     "Oat groats, buckwheat, milk, date gel, flax seeds",
     220, "oatmeal buckwheat porridge healthy breakfast"),

    (2, "Сырники с Сырным Муссом", "Быштак Мусс Менен Сырниктери", "Cheese Pancakes with Cheese Mousse",
     "Творожные сырники с нежным сырным муссом",
     "Назик быштак муссу менен сырниктер",
     "Cottage cheese pancakes with delicate cheese mousse",
     260, "syrniki cottage cheese pancakes mousse"),

    (2, "Шакшука", "Шакшука", "Shakshuka",
     "Куриное яйцо, перец болгарский, лук репчатый, шпинат, сыр моцарелла и пармезан, микс зелень, гренки",
     "Тоок жумурткасы, болгар калемпири, пияз, ысмалак, моцарелла жана пармезан быштактары, аралаш жашылчалар, какталган нан",
     "Chicken egg, bell pepper, onion, spinach, mozzarella and parmesan cheese, mixed greens, croutons",
     260, "shakshuka eggs tomatoes spinach"),

    (2, "Дольче Вита Фирменный Завтрак", "Дольче Вита Таңкы Тамагы", "Dolce Vita Signature Breakfast",
     "Куриные яйца, помидоры канкасе и черри, круглый круассан, листья салата, сыр страчателла, слабосоленая семга, соус брокколи и песто",
     "Тоок жумурткалары, тазаланган жана черри помидорлору, тегерек круассаны, салат жалбырагы, страчателла быштагы, жеңил туздалган семга балыгы, брокколи жана песто соустары",
     "Chicken eggs, concasse and cherry tomatoes, round croissant, salad leaves, stracciatella cheese, lightly salted salmon, broccoli and pesto sauces",
     380, "full breakfast eggs salmon stracciatella croissant"),

    (2, "Блины Домашние", "Үй Куймактары", "Homemade Pancakes",
     "Тонкие домашние блины",
     "Ичке үй куймактары",
     "Thin homemade pancakes",
     150, "russian pancakes blini homemade"),

    (2, "Блины с Творогом", "Быштак Менен Куймак", "Pancakes with Cottage Cheese",
     "Блины с начинкой из творога",
     "Быштак толтурмасы менен куймак",
     "Pancakes with cottage cheese filling",
     180, "blini pancakes cottage cheese filling"),

    (2, "Блины с Мясом", "Эт Менен Куймак", "Pancakes with Meat",
     "Блины с мясной начинкой",
     "Эт толтурмасы менен куймак",
     "Pancakes with meat filling",
     220, "blini pancakes meat filling"),

    (2, "Омлет из Трех Яиц", "Үч Жумурткадан Омлет", "Three-Egg Omelette",
     "Куриные яйца, шпинат, шампиньоны, перец болгарский, лук, помидоры канкасе, сыр Эмилия, гренки, соус песто",
     "Тоок жумурткалары, ысмалак, шампиньон козу карындары, болгар калемпири, пияз, тазаланган помидор, Эмилия быштагы, какталган нан, песто соусу",
     "Chicken eggs, spinach, mushrooms, bell pepper, onion, concasse tomatoes, Emilia cheese, croutons, pesto sauce",
     260, "omelette three eggs vegetables mushrooms"),

    (2, "Глазунья с Овощами", "Жашылча Менен Кууруган Жумуртка", "Fried Eggs with Vegetables",
     "Куриные яйца, шампиньоны, перец болгарский, лук, помидоры канкасе, гренки, соус песто",
     "Тоок жумурткалары, шампиньон козу карындары, болгар калемпири, пияз, тазаланган помидор, какталган нан, песто соусу",
     "Chicken eggs, mushrooms, bell pepper, onion, concasse tomatoes, croutons, pesto sauce",
     260, "fried eggs vegetables mushrooms breakfast"),

    # ── САЛАТЫ (3) ─────────────────────────────────────────────────────────────
    (3, "Буррата с Помидорами", "Помидор Менен Буррата Быштагы", "Burrata with Tomatoes",
     "Сыр Буррата, помидоры, руккола, соус песто",
     "Буррата быштагы, помидор, руккола, пест соусу",
     "Burrata cheese, tomatoes, arugula, pesto sauce",
     420, "burrata cheese tomatoes arugula pesto"),

    (3, "Салат со Свеклой и Сыром Горгонзола", "Кызылча Жана Горгонзола Быштагы Менен Салат", "Beet and Gorgonzola Salad",
     "Свекла, сыр горгонзола, руккола, помидоры, сыр пармезан, кедровые орехи, бальзамический соус",
     "Кызылча, горгонзола быштагы, руккола, помидор, пармезан быштагы, кедр жаңгагы, бальзам соусу",
     "Beet, gorgonzola cheese, arugula, tomatoes, parmesan cheese, pine nuts, balsamic sauce",
     390, "beet salad gorgonzola pine nuts arugula balsamic"),

    (3, "Салат с Морепродуктами", "Деңиз Азыктары Менен Салат", "Seafood Salad",
     "Салат микс, помидоры, перепелиные яйца, семга, кальмары, тигровые креветки, сыр пармезан, цитрусовый соус",
     "Салат аралашмасы, помидор, бедене жумурткасы, семга балыгы, кальмар, креветкалар, пармезан быштагы, цитрус соусу",
     "Mixed salad, tomatoes, quail eggs, salmon, squid, tiger shrimp, parmesan cheese, citrus sauce",
     590, "seafood salad salmon shrimp squid parmesan"),

    (3, "Азиатский Салат с Уткой", "Өрдөк Менен Азия Салаты", "Asian Duck Salad",
     "Утка в панировке, микс салат, помидоры, огурцы, перец болгарский красный, кунжут, заправка на основе соевого соуса",
     "Кургатылган нанга буланып куурулган өрдөк эти, салат аралашмасы, помидор, бадыраң, кызыл болгар калемпири, сейдана, соя соусу",
     "Breaded duck, mixed salad, tomatoes, cucumbers, red bell pepper, sesame, soy-based dressing",
     390, "duck asian salad sesame soy sauce crispy"),

    (3, "Салат с Древесными Грибами (Курица/Говядина)", "Кара Козу Карын Менен Салат (Тоок/Уй Эти)", "Wood Mushroom Salad (Chicken/Beef)",
     "Древесные грибы, курица/говядина, стручковая фасоль, перец болгарский, лук зеленый, чеснок, терияки/кимчи соус, корень имбиря, кинза, кунжут",
     "Кара козу карындары, тоок эти/уй эти, жашыл буурчак, болгар калемпири, жашыл пияз, сарымсак, терияки/кимчи соусу, имбирь тамыры, кинза, сейдана",
     "Wood mushrooms, chicken/beef, green beans, bell pepper, green onion, garlic, teriyaki/kimchi sauce, ginger root, cilantro, sesame",
     390, "wood ear mushroom salad spicy kimchi teriyaki"),

    (3, "Чукка с Креветками", "Креветка Менен Чукка", "Chukka with Shrimp",
     "Морские водоросли Чукка, тигровые креветки, ореховый соус, кунжут",
     "Чукка балырсымалдары, жолборс креветкалары, жаңгак соусу, сейдана",
     "Chukka seaweed, tiger shrimp, nut sauce, sesame",
     480, "chukka seaweed shrimp sesame salad"),

    (3, "Салат с Киноа и Авокадо", "Киноа Жана Авокадо Менен Салат", "Quinoa Avocado Salad",
     "Авокадо, киноа, помидоры, огурцы, руккола, соус",
     "Авокадо, киноа, помидор, бадыраң, руккола, соус",
     "Avocado, quinoa, tomatoes, cucumbers, arugula, sauce",
     390, "quinoa avocado salad healthy arugula"),

    (3, "Греческий Салат", "Грек Салаты", "Greek Salad",
     "Помидоры, огурцы, красный болгарский перец, оливки, маслины, лук красный, микс салат, сыр Фета, долька лимона",
     "Помидор, бадыраң, кызыл болгар калемпири, зайтун, кызыл пияз, аралаш салат, Фета быштагы, лимон",
     "Tomatoes, cucumbers, red bell pepper, olives, red onion, mixed salad, feta cheese, lemon wedge",
     350, "greek salad feta olives tomatoes"),

    (3, "Цезарь с Курицей/с Креветками", "Цезарь Тоок/Креветка", "Caesar with Chicken/Shrimp",
     "Курица/креветки, помидоры, листья салата романо, гренки, сыр Пармезан, соус Цезарь",
     "Тоок эти/креветка, помидор, салат жалбырагы романо, какталган нан, пармезан быштагы, Цезарь соусу",
     "Chicken/shrimp, tomatoes, romaine lettuce leaves, croutons, Parmesan cheese, Caesar dressing",
     380, "caesar salad chicken shrimp romaine parmesan"),

    (3, "Дольче Вита (салат)", "Дольче Вита Салаты", "Dolce Vita Salad",
     "Слабосоленая семга, помидоры канкасе, огурцы, микс салат, яйцо перепелиное, сырные кнели, соус",
     "Жеңил туздалган семга балыгы, тазаланган помидор, бадыраң, аралаш салат, бедене жумурткасы, быштак кнели, соус",
     "Lightly salted salmon, concasse tomatoes, cucumbers, mixed salad, quail egg, cheese dumplings, sauce",
     480, "salmon salad quail egg mixed greens signature"),

    (3, "Салат со Страчателлой", "Страчателла Быштагы Менен Салат", "Stracciatella Salad",
     "Помидоры, сыр Страчателла, руккола, соус песто",
     "Помидор, Страчателла быштагы, руккола, песто соусу",
     "Tomatoes, stracciatella cheese, arugula, pesto sauce",
     390, "stracciatella salad tomatoes arugula pesto"),

    (3, "Лаззат Острый", "Ачуу Лаззат", "Lazzat Spicy Salad",
     "Овощи, говядина отварная, соевый соус",
     "Жашылчалар, кайнатылган уй эти, соя соусу",
     "Vegetables, boiled beef, soy sauce",
     390, "spicy beef salad vegetables soy sauce"),

    (3, "Салат с Баклажанами", "Баклажан Салаты", "Eggplant Salad",
     "Баклажаны, помидоры, лук красный, соус",
     "Баклажан, помидор, кызыл пияз, соус",
     "Eggplant, tomatoes, red onion, sauce",
     350, "eggplant salad roasted tomatoes"),

    (3, "Оливье", "Оливье", "Olivier Salad",
     "Отварной картофель, морковь, говядина, соленые огурцы, яйцо, зеленый горошек, майонез",
     "Бышырылган картөшкө, сабиз, уй эти, туздалган бадыраң, жумуртка, жашыл буурчак, майонез",
     "Boiled potato, carrot, beef, pickled cucumbers, egg, green peas, mayonnaise",
     280, "olivier russian salad potato beef"),

    # ── ЗАКУСКИ (4) ────────────────────────────────────────────────────────────
    (4, "Большое Ассорти Закусок", "Закускалардын Чоң Ассортиси", "Large Appetizer Assortment",
     "Куриные крылышки, мойва, мозговые кости, картофель фри, сырные палочки, карнишоны, соус",
     "Тооктун канаттары, мойва балыгы, чучук сөөктөрү, картөшкө фри, быштак таяқчалары, карнишон бадыраңы, соус",
     "Chicken wings, smelt fish, bone marrow, french fries, cheese sticks, gherkins, sauce",
     890, "appetizer assortment wings fries cheese sticks"),

    (4, "Хумус с Соусом Тахини", "Тахини Соусу Менен Хумус", "Hummus with Tahini Sauce",
     "Нут отварной, паста тахини, сок лимона, зира, чеснок, подается с фокачча",
     "Бышырылган нокот, тахини пастасы, лимон ширеси, зире, сарымсак, фокачча менен берилет",
     "Boiled chickpeas, tahini paste, lemon juice, cumin, garlic, served with focaccia",
     220, "hummus tahini sauce olive oil pita focaccia"),

    (4, "Брускетта с Семгой и Авокадо", "Семга Балыгы Жана Авокадо Менен Брускетасы", "Bruschetta with Salmon and Avocado",
     "Тосты, гуакамоле, семга, руккола",
     "Тост, гуакамол, семга балыгы, руккола",
     "Toast, guacamole, salmon, arugula",
     420, "bruschetta salmon avocado guacamole toast"),

    (4, "Мозговые Кости", "Чучук Сөөктөрү", "Bone Marrow",
     "Мозговые кости со специями",
     "Татымалдар кошулган чучук сөөктөрү",
     "Bone marrow with spices",
     520, "bone marrow roasted spices bread"),

    (4, "Брускетта со Страчателлой и Помидорами", "Страчателла Быштагы Жана Помидор Менен Брускетасы", "Bruschetta with Stracciatella and Tomatoes",
     "Страчателла, помидоры, руккола, соус песто",
     "Страчателла быштагы, помидор, руккола, песто соусу",
     "Stracciatella, tomatoes, arugula, pesto sauce",
     280, "bruschetta stracciatella cheese tomatoes pesto"),

    (4, "Баклажаны Фри", "Баклажан Фри", "Eggplant Fries",
     "Жареные баклажаны во фритюре",
     "Фритюрде куурулган баклажан",
     "Deep fried eggplant",
     380, "eggplant fries fried crispy golden"),

    (4, "Мясное Ассорти", "Эт Топтому", "Meat Assortment",
     "Чучук, вяленая говядина, куриный рулет, говяжья нарезка со специями",
     "Чучук, сүрсүтүлгөн уй эти, тоок оролмосу, татымал кошулган уй эти кесимдери",
     "Chuchuk sausage, dried beef, chicken roll, spiced beef cold cuts",
     890, "meat charcuterie platter assortment cold cuts"),

    (4, "Фруктовая Тарелка", "Жемиштер Табагы", "Fruit Platter",
     "Яблоко, груша, банан, виноград, апельсин, киви, ананас",
     "Алма, алмурут, банан, жүзүм, апельсин, киви, ананас",
     "Apple, pear, banana, grapes, orange, kiwi, pineapple",
     780, "fruit platter fresh seasonal tropical"),

    # ── СУПЫ (5) ───────────────────────────────────────────────────────────────
    (5, "Уха из Семги", "Семга Балык Шорпосу", "Salmon Fish Soup",
     "Семга, овощи, специи",
     "Семга балыгы, жашылчалар, татымалдар",
     "Salmon, vegetables, spices",
     260, "salmon fish soup clear broth"),

    (5, "Пити по-Бакински", "Баку Питиси", "Baku-Style Piti",
     "Баранина, нут, лук, специи",
     "Кой эти, нокот, пияз, татымалдар",
     "Lamb, chickpeas, onion, spices",
     420, "piti azerbaijani lamb soup clay pot"),

    (5, "Крем Суп из Тыквы", "Ашкабак Крем Шорпосу", "Pumpkin Cream Soup",
     "Тыква, чеснок, корень имбиря",
     "Ашкабак, сарымсак, имбирдин тамыры",
     "Pumpkin, garlic, ginger root",
     240, "pumpkin cream soup orange"),

    (5, "Том-Ям с Креветками/с Семгой", "Том-Ям Креветка Же Семга Балыгы Менен", "Tom Yam with Shrimp/Salmon",
     "Креветки, кальмары, семга, мидии, грибы шампиньоны, кинза, вяленые помидоры, кокосовое молоко, подается с рисом",
     "Креветка, кальмар, семга балыгы, мидии, шампиньон козу карындары, кинза, сурсутулген помидор, кокос суту, күрүч менен берилет",
     "Shrimp, squid, salmon, mussels, champignon mushrooms, cilantro, sun-dried tomatoes, coconut milk, served with rice",
     650, "tom yum soup shrimp coconut milk"),

    (5, "Фасолевый Суп из Молодого Ягненка", "Жаш Козудан Жасалган Буурчак Шорпо", "Young Lamb Bean Soup",
     "Фасоль, лук, стебель сельдерея, морковь, мясо молодого ягненка, вяленые помидоры",
     "Буурчак, пияз, сельдерей сабагы, сабиз, жаш козунун эти, сурсутулген помидор",
     "Beans, onion, celery stalk, carrot, young lamb meat, sun-dried tomatoes",
     430, "lamb bean soup hearty"),

    (5, "Кимчи Тиге Острый Суп с Говядиной", "Кимчи Тиге Ачуу Уй Этинен Суюк Тамагы", "Kimchi Jjigae Spicy Beef Soup",
     "Говяжий бульон, корень имбиря, чеснок, соевый соус, кимчи соус, говядина, древесные грибы, кинза, кунжут, кимчи салат, лук репчатый, лапша стеклянная, тофу",
     "Уйдун шорпосу, имбирдин тамыры, сарымсак, соя соусу, кимчи соусу, уй эти, кара козу карындар, кинза, сейдана, кимчи салаты, пияз, кесме, тофу",
     "Beef broth, ginger root, garlic, soy sauce, kimchi sauce, beef, wood mushrooms, cilantro, sesame, kimchi, onion, glass noodles, tofu",
     420, "kimchi jjigae korean beef soup spicy"),

    (5, "Суп Куриный", "Тоок Шорпо", "Chicken Soup",
     "Курица, домашняя лапша, морковь, лук, перепелиные яйца",
     "Тоок эти, үй кесме, сабиз, пияз, бөдөнө жумурткалары",
     "Chicken, homemade noodles, carrot, onion, quail eggs",
     230, "chicken soup noodles homemade"),

    (5, "Окрошка", "Окрошка", "Okroshka",
     "Куриное филе, картофель, куриное яйцо, огурцы, редиска, кефир",
     "Тоок эти, картөшкө, тоок жумурткасы, бадыраң, кызыл шалгам, айран",
     "Chicken fillet, potato, egg, cucumbers, radish, kefir",
     220, "okroshka cold soup russian kefir"),

    (5, "Суп Чечевичный", "Жасмык Шорпосу", "Lentil Soup",
     "Чечевица, лук, морковь, томатная паста",
     "Жасмык, пияз, сабиз, томат пастасы",
     "Lentil, onion, carrot, tomato paste",
     220, "lentil soup red orange"),

    (5, "Рамен Курица/Говядина/Ассорти", "Рамен Тоок/Уй Эти/Ассорти", "Ramen Chicken/Beef/Assorted",
     "Рамен с куриным или говяжьим бульоном, лапша, яйцо, нори",
     "Тоок же уй эти шорпосу менен рамен, кесме, жумуртка, нори",
     "Ramen with chicken or beef broth, noodles, egg, nori",
     340, "ramen noodle soup japanese"),

    (5, "Борщ с Говядиной", "Уй Эти Менен Борщ", "Beef Borscht",
     "Говядина, морковь, лук, капуста, свекла, картофель, чеснок, томатная паста, говяжий бульон, уксус",
     "Уй эти, сабиз, пияз, капуста, кызылча, картөшкө, сарымсак, томат пастасы, уй шорпосу, уксус",
     "Beef, carrot, onion, cabbage, beet, potato, garlic, tomato paste, beef broth, vinegar",
     260, "borscht red beet soup beef"),

    (5, "Бухарская Шурпа", "Бухара Шорпо", "Bukhara Shurpa",
     "Говядина отварная, картофель, перец болгарский, говяжий бульон",
     "Кайнатылган уй эти, картөшкө, болгар калемпири, уй шорпосу",
     "Boiled beef, potato, bell pepper, beef broth",
     340, "shurpa uzbek beef soup"),

    (5, "Крем Суп из Брокколи и Цветной Капусты", "Брокколиден Жана Тустуу Капустадан Жасалган Суюк Тамагы", "Broccoli and Cauliflower Cream Soup",
     "Брокколи, цветная капуста, семга, сливки, лук",
     "Брокколи, тустуу капуста, семга балыгы, каймак, пияз",
     "Broccoli, cauliflower, salmon, cream, onion",
     220, "broccoli cauliflower cream soup green"),

    # ── ПАСТА (6) ──────────────────────────────────────────────────────────────
    (6, "Паста Дольче Вита", "Дольче Вита Пастасы", "Dolce Vita Pasta",
     "Спагетти, сыр пармезан, грудинка копченая, трюфельная паста, сливки. Подача в сырной головке",
     "Спагетти, пармезан быштагы, ышталган эт, трюфель пастасы, каймак. Быштак идишинде даярдалат",
     "Spaghetti, parmesan cheese, smoked bacon, truffle paste, cream. Served in cheese wheel",
     690, "pasta cheese wheel truffle parmesan"),

    (6, "Паста с Морепродуктами", "Дениз Азыктары Менен Паста", "Seafood Pasta",
     "Спагетти, лук, чеснок, перец чили, креветка, семга, мидии, сливки",
     "Спагетти, пияз, сарымсак, чили калемпири, креветка, семга балыгы, мидии, каймак",
     "Spaghetti, onion, garlic, chili pepper, shrimp, salmon, mussels, cream",
     590, "seafood pasta spaghetti shrimp mussels"),

    (6, "Тальятелле с Креветками и Рукколой", "Креветка Жана Руккола Менен Тальятелле Макарону", "Tagliatelle with Shrimp and Arugula",
     "Тальятелле, креветки, лук, чеснок, соус томатный, сливки, помидоры черри, руккола",
     "Тальятелле, креветкалар, пияз, сарымсак, томат соусу, каймак, черри помидору, руккола",
     "Tagliatelle, shrimp, onion, garlic, tomato sauce, cream, cherry tomatoes, arugula",
     490, "tagliatelle shrimp arugula pasta"),

    (6, "Лазанья", "Лазанья", "Lasagna",
     "Паста лазанья, соус бешамель, говяжий фарш, соус томатный, сыр моцарелла и пармезан",
     "Лазанья пастасы, бешамель соусу, майдаланган уй эти, томат соусу, моцарелла жана пармезан быштагы",
     "Lasagna pasta, béchamel sauce, ground beef, tomato sauce, mozzarella and parmesan cheese",
     480, "lasagna beef bolognese bechamel"),

    (6, "Равиолли с Бурратой", "Равиолли Буррата Менен", "Ravioli with Burrata",
     "Тесто, сыр буррата, сливки, трюфельное паста, сыр брынза и пармезан",
     "Камыр, буррата быштагы, каймак, трюфель пастасы, брынза жана пармезан быштагы",
     "Dough, burrata cheese, cream, truffle paste, brynza and parmesan cheese",
     490, "ravioli burrata truffle cream sauce"),

    (6, "Равиолли со Шпинатом", "Равиолли Ысмалак Менен", "Ravioli with Spinach",
     "Тесто, сыр брынза, шпинат, сливки, лук, помидоры, сыр пармезан",
     "Камыр, брынза быштагы, ысмалак, каймак, пияз, помидор, пармезан быштагы",
     "Dough, brynza cheese, spinach, cream, onion, tomatoes, parmesan cheese",
     380, "ravioli spinach cream cheese sauce"),

    (6, "Спагетти с Трюфельным Соусом", "Трюфель Соусу Менен Спагетти", "Spaghetti with Truffle Sauce",
     "Паста спагетти, сливки, трюфельная паста, сыр пармезан",
     "Спагетти макарону, каймак, трюфель пастасы, пармезан быштагы",
     "Spaghetti pasta, cream, truffle paste, parmesan cheese",
     360, "spaghetti truffle sauce parmesan"),

    (6, "Пенне Арабьята", "Пенне Арабьята", "Penne Arrabbiata",
     "Паста пенне, томатный соус, чеснок, перец чили, сыр пармезан, зелень",
     "Пенне макарону, томат соусу, сарымсак, чили калемпири, пармезан быштагы, жашылдыктар",
     "Penne pasta, tomato sauce, garlic, chili pepper, parmesan cheese, herbs",
     320, "penne arrabbiata spicy tomato sauce"),

    (6, "Карбонара с Говядиной с Курицей", "Карбонара Ышталган Уй Эти Менен Тоок Эти Менен", "Carbonara with Beef and Chicken",
     "Паста спагетти, сливки, говяжие вырезки, яичный желток, лук, сыр пармезан",
     "Спагетти макарону, каймак, уй эти, жумурткалын сарысы, пияз, пармезан быштагы",
     "Spaghetti pasta, cream, beef fillet, egg yolk, onion, parmesan cheese",
     490, "carbonara pasta bacon egg parmesan"),

    (6, "Фетучини с Семгой и Брокколи", "Семга Балыгы Жана Брокколи Менен Фетучини", "Fettuccine with Salmon and Broccoli",
     "Макарон фетучини, семга, лук, брокколи, сливки",
     "Фетучини макарону, семга балыгы, пияз, брокколи, каймак",
     "Fettuccine pasta, salmon, onion, broccoli, cream",
     580, "fettuccine salmon broccoli cream sauce"),

    (6, "Спагетти Болоньезе", "Болоньезе Спагеттиси", "Spaghetti Bolognese",
     "Спагетти, фарш болоньезе, соус томатный, сыр пармезан",
     "Спагетти, болоньезе майдаланган эти, томат соусу, пармезан бийштагы",
     "Spaghetti, bolognese ground meat, tomato sauce, parmesan cheese",
     480, "spaghetti bolognese meat sauce"),

    (6, "Фарфалле с Курицей и Грибами", "Фарфалле Тоок Эти Жана Козу Карындар Менен", "Farfalle with Chicken and Mushrooms",
     "Паста фарфалле, куриное филе, грибы шампиньоны, лук, чеснок, сливки",
     "Фарфалле макарону, тоок эти, шампиньон козу карындары, пияз, сарымсак, каймак",
     "Farfalle pasta, chicken fillet, champignon mushrooms, onion, garlic, cream",
     440, "farfalle bow tie pasta chicken mushroom cream"),

    # ── ГОРЯЧИЕ БЛЮДА (7) ──────────────────────────────────────────────────────
    (7, "Утиное Конфи", "Өрдөк Конфиси", "Duck Confit",
     "Утиная ножка, пюре из батата, специи, соус демиглас",
     "Өрдөк буту, батат пюреси, татымалдар, демиглас соусу",
     "Duck leg, sweet potato purée, spices, demi-glace sauce",
     590, "duck confit sweet potato puree demiglace"),

    (7, "Стейк из Семги", "Семга Балыгынан Стейк", "Salmon Steak",
     "Семга, кабачки, шампиньоны, апельсины, помидоры черри",
     "Семга балыгы, шампиньон козу карыны, апельсин, черри помидору",
     "Salmon, zucchini, champignon mushrooms, oranges, cherry tomatoes",
     820, "salmon steak fillet grilled"),

    (7, "Семга с Овощами", "Семга Балыгы Жашылчалар Менен", "Salmon with Vegetables",
     "Семга, перец болгарский, фасоль стручковая, кабачки, имбирный дресинг, икра",
     "Семга балыгы, болгар калемпири, жашыл буурчак, кабак, имбирь дрессинги, икра",
     "Salmon, bell pepper, green beans, zucchini, ginger dressing, caviar",
     790, "salmon fillet vegetables healthy grilled"),

    (7, "Фрикадельки", "Фрикадельки", "Meatballs",
     "Говяжие фрикадельки, пюре, микс салат, сливочный соус",
     "Уй этинен фрикадельки, пюре, салат аралашмасы, каймак соусу",
     "Beef meatballs, mashed potatoes, mixed salad, cream sauce",
     480, "meatballs beef mashed potato cream sauce"),

    (7, "Кремлевские Котлеты", "Кремль Котлетасы", "Kremlin Cutlets",
     "Говядина, полба, паста трюфель, шампиньоны, соус демиглас",
     "Уй эти, полба, трюфель пастасы, шампиньон козу карыны, демиглас соусу",
     "Beef, spelt, truffle paste, champignon mushrooms, demi-glace sauce",
     460, "beef cutlet truffle demiglace"),

    (7, "Медальоны с Овощами", "Медальондор Жашылчалар Менен", "Medallions with Vegetables",
     "Бон филе, жареные овощи на гриле, соус демиглас",
     "Бон филе уй этинин жумшак кесиги, грильде куурулган жашылчалар, демиглас соусу",
     "Beef tenderloin, grilled vegetables, demi-glace sauce",
     890, "beef medallions tenderloin grilled vegetables"),

    (7, "Кебаб с Сыром и Фокачча", "Кебаб Быштак Менен Жана Фокачча", "Kebab with Cheese and Focaccia",
     "Говядина, баранина, фокачча, лук, халапеньо",
     "Уй, кой эти, фокачча, пияз, халапеньо",
     "Beef, lamb, focaccia, onion, jalapeño",
     480, "kebab flatbread cheese onion"),

    (7, "Курица по-Милански", "Милан Тоок Котлетасы", "Milan-Style Chicken",
     "Отбивная курица, фри, микс салат, сырный соус",
     "Жалпайтылган тоок эти, фри, салат аралашмасы, быштак соусу",
     "Chicken schnitzel, fries, mixed salad, cheese sauce",
     390, "chicken schnitzel milanese fries"),

    (7, "Асадо с Ризотто Баранина/Говядина", "Асадо Ризотто Менен Кой/Уй Эти", "Asado with Risotto Lamb/Beef",
     "Говяжьи ребра/баранье седло, ризотто, соус демиглас",
     "Уйдун кабыргасы/козу омурткасы, ризотто, демиглас соусу",
     "Beef ribs/lamb saddle, risotto, demi-glace sauce",
     890, "beef ribs asado risotto"),

    (7, "Голень Ягненка", "Козунун Шыйрагы", "Lamb Shank",
     "Голень ягненка, пюре, жареные овощи, соус демиглас",
     "Козунун шыйрагы, пюре, куурулган жашылчалар, демиглас соусу",
     "Lamb shank, mashed potatoes, roasted vegetables, demi-glace sauce",
     980, "lamb shank braised mashed potato demiglace"),

    (7, "Куриные Котлеты", "Тоок Котлетасы", "Chicken Cutlets",
     "Нежные куриные котлеты с гарниром",
     "Жумшак тоок котлеталары гарнир менен",
     "Tender chicken cutlets with side dish",
     420, "chicken cutlets tender juicy"),

    (7, "Хинкали", "Хинкали", "Khinkali",
     "Грузинские пельмени с мясной начинкой",
     "Эт толтурмасы менен грузиялык пельмендер",
     "Georgian dumplings with meat filling",
     440, "khinkali georgian dumplings"),

    (7, "Бефстроганов с Говядиной/с Курицей", "Уйдун/Тооктун Эти Менен Бефстроганов", "Beef/Chicken Stroganoff",
     "Говядина или курица в сливочном соусе с грибами",
     "Сливочный соусу жана козу карындар менен уй же тоок эти",
     "Beef or chicken in cream sauce with mushrooms",
     520, "beef stroganoff cream sauce mushroom"),

    (7, "Курица в Кисло-сладком Соусе", "Тоок Эти Кычкыл-Таттуу Соусунда", "Chicken in Sweet-and-Sour Sauce",
     "Курица в кисло-сладком соусе с овощами по-азиатски",
     "Азиялык жашылчалар менен кычкыл-таттуу соусунда тоок эти",
     "Chicken in sweet-and-sour sauce with Asian vegetables",
     480, "sweet sour chicken asian vegetables"),

    # ── ШАШЛЫКИ ПО-АЗЕРБАЙДЖАНСКИ (8) ─────────────────────────────────────────
    (8, "Баранина Мякоть", "Койдун Сулп Этинен", "Lamb Tenderloin Shashlik",
     "Шашлык из баранины мякоти по-азербайджански",
     "Азербайжан стилинде койдун сулп этинен шишкебек",
     "Azerbaijani-style lamb tenderloin shashlik",
     580, "lamb shashlik azerbaijani grill skewer"),

    (8, "Баранина «Антрекот» Ребрышки", "Кой Этинен «Антрекот» Кабыргалар", "Lamb Rib Chops",
     "Шашлык из бараньих рёбер антрекот",
     "Кой этинен антрекот кабыргалар шишкебеги",
     "Lamb rib chop shashlik",
     660, "lamb rib chops grilled skewer"),

    (8, "Баранина «Особый»", "Кой Этинен «Өзгөчө»", "Special Lamb",
     "Шашлык из особой части баранины",
     "Койдун өзгөчө бөлүгүнөн шишкебек",
     "Shashlik from special cut of lamb",
     660, "lamb special cut grilled"),

    (8, "Говядина", "Уй Этинен", "Beef Shashlik",
     "Шашлык из говядины по-азербайджански",
     "Азербайжан стилинде уй этинен шишкебек",
     "Azerbaijani-style beef shashlik",
     580, "beef shashlik skewer grilled"),

    (8, "Люля Кебаб по-Азербайджански в Лаваше", "Лавашта Оролгон Азербайжан Люля Кебабы", "Azerbaijani Lula Kebab in Lavash",
     "Люля кебаб из баранины и говядины в лаваше",
     "Кой жана уй этинен лавашта оролгон азербайжан люля кебабы",
     "Lamb and beef lula kebab in lavash bread",
     460, "lula kebab azerbaijani lavash bread"),

    (8, "Куриное Бедро", "Тооктун Сан Эти", "Chicken Thigh Shashlik",
     "Шашлык из куриного бедра",
     "Тооктун сан этинен шишкебек",
     "Chicken thigh shashlik",
     380, "chicken thigh shashlik grilled"),

    (8, "Куриные Крылышки", "Тоок Канатчалары", "Chicken Wings",
     "Шашлык из куриных крылышек",
     "Тоок канатчаларынан шишкебек",
     "Chicken wing shashlik",
     380, "chicken wings grilled shashlik"),

    (8, "Куриное Филе", "Тоок Филеси", "Chicken Fillet Shashlik",
     "Шашлык из куриного филе",
     "Тоок филесинен шишкебек",
     "Chicken fillet shashlik",
     380, "chicken fillet shashlik skewer grilled"),

    (8, "Грибы Шампиньоны", "Шампиньон Козу Карындары", "Champignon Mushroom Shashlik",
     "Шашлык из грибов шампиньонов",
     "Шампиньон козу карындарынан шишкебек",
     "Champignon mushroom shashlik",
     380, "mushroom shashlik grilled skewer"),

    (8, "Овощной Шашлык", "Жашылчалар Менен Шишкебек", "Vegetable Shashlik",
     "Шашлык из сезонных овощей",
     "Мезгилдик жашылчалардан шишкебек",
     "Seasonal vegetable shashlik",
     260, "vegetable kebab grilled skewer"),

    (8, "Ассорти «Дольче Вита»", "«Дольче Вита» Ассортиси", "Dolce Vita Shashlik Assortment",
     "Баранина мякоть 5п, Говядина 5п, Люля кебаб 5п, Куриное бедро 3п, Антрекот 2п, Куриные крылышки 5п, Куриное филе 5п, Грибы 5п, Овощи 5п, Картофель 5п",
     "Койдун сулп этинен 5п, Уй этинен 5п, Люля кебаб 5п, Тооктун сан эти 3п, Антрекот 2п, Тоок канатчалары 5п, Тоок филеси 5п, Козу карындар 5п, Жашылча менен 5п, Картөшкө 5п",
     "Lamb tenderloin 5pcs, Beef 5pcs, Lula kebab 5pcs, Chicken thigh 3pcs, Antrecot 2pcs, Chicken wings 5pcs, Chicken fillet 5pcs, Mushrooms 5pcs, Vegetables 5pcs, Potato 5pcs",
     18000, "shashlik assortment large platter mix meat"),

    (8, "Ассорти «Ширваншах»", "«Ширваншах» Ассортиси", "Shirvanshah Shashlik Assortment",
     "Баранина мякоть 3п, Говядина 3п, Люля кебаб 5п, Куриное бедро 3п, Куриные крылышки 4п, Куриное филе 3п, Грибы 3п, Овощи 3п, Картофель 3п",
     "Койдун сулп этинен 3п, Уй этинен 3п, Люля кебаб 5п, Тооктун сан эти 3п, Тоок канатчалары 4п, Тоок филеси 3п, Козу карындар 3п, Жашылча менен 3п, Картөшкө 3п",
     "Lamb 3pcs, Beef 3pcs, Lula kebab 5pcs, Chicken thigh 3pcs, Chicken wings 4pcs, Chicken fillet 3pcs, Mushrooms 3pcs, Vegetables 3pcs, Potato 3pcs",
     12000, "shashlik assortment medium platter"),

    (8, "Ассорти «Нар»", "«Нар» Ассортиси", "Nar Shashlik Assortment",
     "Баранина мякоть 2п, Говядина 2п, Люля кебаб 3п, Куриное филе 3п, Куриные крылышки 3п, Грибы 3п, Овощи 3п, Картофель 3п",
     "Койдун сулп этинен 2п, Уй этинен 2п, Люля кебаб 3п, Тоок филеси 3п, Тоок канатчалары 3п, Козу карындар 3п, Жашылча менен 3п, Картөшкө 3п",
     "Lamb 2pcs, Beef 2pcs, Lula kebab 3pcs, Chicken fillet 3pcs, Chicken wings 3pcs, Mushrooms 3pcs, Vegetables 3pcs, Potato 3pcs",
     8300, "shashlik assortment small platter"),

    # ── СТЕЙКИ (9) ─────────────────────────────────────────────────────────────
    (9, "Томагавк", "Томагавк", "Tomahawk Steak",
     "Это стейк Рибай с целой реберной костью. Гарнир на гриле: кабачки, баклажан, перец болгарский, помидоры, лук, шампиньоны",
     "Бул бүтүн кабырга сөөгү менен рибай стейки. Грильде бышырылган гарнир: кабактар, баклажан, болгар калемпири, помидор, пияз, шампиньон козу карындар",
     "This is a Ribeye steak with the full rib bone. Grilled side dish: zucchini, eggplant, bell pepper, tomatoes, onion, champignon mushrooms",
     1900, "tomahawk steak ribeye bone grilled"),

    (9, "Ти-Бон", "Ти-Бон", "T-Bone Steak",
     "Стейк Т-образной кости, состоит из двух видов мяса – вырезки и тонкого края. Гарнир на гриле: кабачки, баклажан, перец болгарский, помидоры, лук, шампиньон",
     "Т сөөгү менен стейк, эттин эки түрүнөн турат – жумшак кесиги жана жука чети. Грильде бышырылган гарнир: кабактар, баклажан, болгар калемпири, помидор, пияз, шампиньон козу карындар",
     "T-bone steak with two types of meat – tenderloin and strip. Grilled side dish: zucchini, eggplant, bell pepper, tomatoes, onion, champignon mushrooms",
     1190, "t-bone steak grilled restaurant"),

    (9, "Рибай", "Рибай", "Ribeye Steak",
     "Самый мясистый, мраморный отруб из стейков. Гарнир на гриле: кабачки, баклажан, перец болгарский, помидоры, лук, шампиньоны",
     "Эң эттүү, мрамор кесилген стейк. Грильде бышырылган гарнир: кабактар, баклажан, болгар калемпири, помидор, пияз, шампиньон козу карындар",
     "The most meaty, marbled steak cut. Grilled side dish: zucchini, eggplant, bell pepper, tomatoes, onion, champignon mushrooms",
     1190, "ribeye steak marbled grilled restaurant"),

    # ── БУРГЕРЫ (10) ───────────────────────────────────────────────────────────
    (10, "Бургер с Фри Говядина", "Фри Менен Бургер Уй Эти", "Beef Burger with Fries",
     "Говяжья котлета, булочка, свежие овощи, соус, картофель фри",
     "Уй этинен котлета, будка, жаңы жашылчалар, соус, картөшкө фри",
     "Beef patty, bun, fresh vegetables, sauce, french fries",
     420, "beef burger classic fries"),

    (10, "Бургер с Фри Курица", "Фри Менен Бургер Тоок Эти", "Chicken Burger with Fries",
     "Куриная котлета, булочка, свежие овощи, соус, картофель фри",
     "Тоок этинен котлета, будка, жаңы жашылчалар, соус, картөшкө фри",
     "Chicken patty, bun, fresh vegetables, sauce, french fries",
     320, "chicken burger fries"),

    (10, "Чизбургер с Картофелем по-Деревенски Говядина", "Кыштак Картөшкөсү Менен Чизбургер Уй Эти", "Beef Cheeseburger with Country-Style Potato",
     "Говяжья котлета, сыр, булочка, картофель по-деревенски",
     "Уй этинен котлета, быштак, будка, кыштак картөшкөсү",
     "Beef patty, cheese, bun, country-style potato",
     440, "cheeseburger beef country potato"),

    (10, "Чизбургер с Картофелем по-Деревенски Курица", "Кыштак Картөшкөсү Менен Чизбургер Тоок", "Chicken Cheeseburger with Country-Style Potato",
     "Куриная котлета, сыр, булочка, картофель по-деревенски",
     "Тоок этинен котлета, быштак, будка, кыштак картөшкөсү",
     "Chicken patty, cheese, bun, country-style potato",
     340, "chicken cheeseburger potato"),

    # ── РОЛЛЫ (11) ─────────────────────────────────────────────────────────────
    (11, "Филадельфия с Чуккой", "Филадельфия Чукка Менен", "Philadelphia with Chukka",
     "Рис, семга, сыр творожный, чукка, нори, огурцы, ореховый соус",
     "Күрүч, семга балыгы, быштак, чукка, нори, бадыраң, жаңгак соусу",
     "Rice, salmon, cream cheese, chukka seaweed, nori, cucumbers, walnut sauce",
     520, "philadelphia roll chukka seaweed salmon"),

    (11, "Филадельфия Роял", "Филадельфия Роял", "Philadelphia Royal",
     "Рис, семга, сыр творожный, угорь, икра, нори, огурцы",
     "Күрүч, семга балыгы, быштак, жылан балыгы, икра, нори, бадыраң",
     "Rice, salmon, cream cheese, eel, caviar, nori, cucumbers",
     580, "philadelphia roll eel caviar salmon"),

    (11, "Эбби Темпура", "Эбби Темпура", "Ebi Tempura Roll",
     "Креветки в кляре, авокадо, тобико, рис, спайси соус, нори",
     "Камырга буланып куурулган креветкалар, авокадо, тобико, күрүч, ачуу соус, нори",
     "Battered shrimp, avocado, tobiko, rice, spicy sauce, nori",
     480, "ebi tempura shrimp roll"),

    (11, "Филадельфия Ассорти", "Филадельфия Ассортиси", "Philadelphia Assortment",
     "Семга, угорь, курица, рис, сыр творожный, огурцы, спайси соус, перепелиные яйца, нори",
     "Семга балыгы, жылан балыгы, тоок эти, күрүч, быштак, бадыраң, ачуу соус, бөдөнө жумурткасы, нори",
     "Salmon, eel, chicken, rice, cream cheese, cucumbers, spicy sauce, quail eggs, nori",
     590, "philadelphia assortment roll salmon eel"),

    (11, "Ролл Кранч", "Кранч Роллдор", "Crunch Roll",
     "Рис, семга, сыр творожный, нори, огурцы, панировка",
     "Күрүч, семга балыгы, быштак, нори, бадыраң, панировка",
     "Rice, salmon, cream cheese, nori, cucumbers, breadcrumbs",
     420, "crunch roll salmon crispy"),

    (11, "Роллы с Угрем и Сыром Чеддер", "Жылан Балыгы Жана Чеддер Быштагы Менен Роллдор", "Eel and Cheddar Cheese Rolls",
     "Семга, авокадо, рис, угорь, сыр чеддер, тобико",
     "Семга балыгы, авокадо, күрүч, жылан балыгы, чеддер быштагы, тобико икрасы",
     "Salmon, avocado, rice, eel, cheddar cheese, tobiko",
     480, "eel cheddar cheese roll sushi"),

    (11, "Запеченные Роллы с Семгой и Угрем", "Семга Жана Жылан Балыгы Менен Бышырылган Роллдор", "Baked Salmon and Eel Rolls",
     "Рис, семга, угорь, сыр творожный, тобико, нори, огурцы",
     "Күрүч, семга балыгы, жылан балыгы, быштак, тобико, нори, бадыраң",
     "Rice, salmon, eel, cream cheese, tobiko, nori, cucumbers",
     550, "baked roll salmon eel cream cheese"),

    (11, "Калифорния с Семгой", "Калифорния Семга Балыгы Менен", "California with Salmon",
     "Рис, сыр творожный, нори, огурцы, тобико, семга",
     "Күрүч, быштак, нори, бадыраң, тобико, семга балыгы",
     "Rice, cream cheese, nori, cucumbers, tobiko, salmon",
     420, "california roll salmon tobiko"),

    (11, "Ролл Светофор", "Тустуу Роллдор", "Traffic Light Roll",
     "Семга, угорь, рис, нори, омлет, сыр творожный, соус спайси, икра красная, соус унаги, кунжут",
     "Семга балыгы, жылан балыгы, күрүч, нори, омлет, быштак, ачуу соус, кызыл икра, унаги соусу, сейдана",
     "Salmon, eel, rice, nori, omelette, cream cheese, spicy sauce, red caviar, unagi sauce, sesame",
     480, "colorful sushi roll traffic light"),

    (11, "Дракон Лайт", "Дракон Лайт", "Dragon Lite Roll",
     "Рис, угорь, сыр творожный, нори, огурцы",
     "Күрүч, жылан балыгы, быштак, нори, бадыраң",
     "Rice, eel, cream cheese, nori, cucumbers",
     420, "dragon roll eel avocado sushi"),

    (11, "Дольче Вита Горячий Ролл", "Дольче Вита Ысык Роллдор", "Dolce Vita Hot Roll",
     "Семга жаренная, рис, сыр творожный, угорь, панировка, кляр, нори",
     "Куурулган семга балыгы, күрүч, быштак, жылан балыгы, панировка, суюк камыр, нори",
     "Fried salmon, rice, cream cheese, eel, breadcrumbs, batter, nori",
     460, "hot roll baked fried salmon cream cheese"),

    (11, "Темпура с Семгой", "Темпура Семга Балыгы Менен", "Tempura with Salmon",
     "Семга, рис, огурцы, творожный сыр кремметто, нори, кляр",
     "Семга балыгы, күрүч, бадыраң, кремметто быштагы, нори, камырга буланып куурулган",
     "Salmon, rice, cucumbers, cremetto cream cheese, nori, tempura batter",
     420, "tempura roll salmon crispy batter"),

    (11, "Филадельфия Классик", "Филадельфия", "Philadelphia Classic",
     "Рис, семга, сыр творожный, огурцы",
     "Күрүч, семга балыгы, быштак, бадыраң",
     "Rice, salmon, cream cheese, cucumbers",
     460, "philadelphia classic roll salmon cucumber"),

    (11, "Сет с Семгой", "Семга Балыгы Менен Топтому", "Salmon Set",
     "Калифорния с семгой, филадельфия с чуккой, запеченные роллы с семгой, темпура с семгой, суши с семгой",
     "Калифорния семга балыгы менен, филадельфия чукка менен, семга балыгы менен бышырылган роллдор, темпура семга балыгы менен, суши семга балыгы менен",
     "California with salmon, philadelphia with chukka, baked salmon rolls, tempura with salmon, sushi with salmon",
     1750, "salmon sushi roll set assortment"),

    (11, "Сет с Угрем", "Жылан Балыгы Менен Топтому", "Eel Set",
     "Дракон лайт, роллы с угрем и сыром чеддер, запеченные роллы с угрем, темпура с угрем, суши с угрем",
     "Дракон лайт, жылан балыгы жана чеддер быштагы менен роллдор, жылан балыгы менен бышырылган роллдор, темпура жылан балык менен, суши жылан балыгы менен",
     "Dragon lite, eel and cheddar cheese rolls, baked eel rolls, tempura with eel, sushi with eel",
     1750, "eel sushi roll set unagi"),

    (11, "Горячий Сет", "Ысык Топтом", "Hot Set",
     "Запеченные роллы с семгой и угрем, темпура с курицей, филадельфия роял, темпура с угрем, гунканы с крабом",
     "Семга жана жылан балыгы менен бышырылган роллдор, тоок эти менен темпура, филадельфия роял, темпура жылан балык менен, краб менен гунканлар",
     "Baked salmon and eel rolls, chicken tempura, philadelphia royal, eel tempura, gunkan with crab",
     1750, "hot sushi set baked rolls"),

    (11, "Сет Большой", "Чоң Топтом", "Big Set",
     "Дракон лайт, филадельфия с семгой, запеченные роллы с семгой и угрем, эбби темпура, ролл кранч, красочные роллы, гунканы с курицей",
     "Дракон лайт, филадельфия семга балыгы менен, семга жана жылан балыгы менен бышырылган роллдор, эбби темпура, кранч роллдор, тустуу роллдор, тоок эти менен гункандар",
     "Dragon lite, philadelphia with salmon, baked salmon and eel rolls, ebi tempura, crunch roll, colorful rolls, gunkan with chicken",
     2650, "big sushi set assortment rolls"),

    # ── ДЕСЕРТЫ (12) ───────────────────────────────────────────────────────────
    (12, "Ягодная Тарталетка", "Мөмөлүү Тарталеткасы", "Berry Tartlet",
     "Тарталетка с кремом и свежими ягодами",
     "Кремдин жана жаңы мөмөлөрдүн менен тарталетка",
     "Tartlet with cream and fresh berries",
     280, "berry tartlet fresh cream pastry"),

    (12, "Фисташковый Десерт", "Мисте Десерти", "Pistachio Dessert",
     "Нежный фисташковый десерт",
     "Назик мисте десерти",
     "Delicate pistachio dessert",
     320, "pistachio dessert green cake"),

    (12, "Ягодный Чизкейк", "Мөмөлүү Чизкейк", "Berry Cheesecake",
     "Нежный чизкейк с ягодным топпингом",
     "Мөмө топпинги менен назик чизкейк",
     "Delicate cheesecake with berry topping",
     350, "berry cheesecake cream cheese"),

    (12, "Немецкий Шоколад", "Немисче Шоколад", "German Chocolate",
     "Шоколадный десерт по-немецки",
     "Немисче стилинде шоколад десерти",
     "German-style chocolate dessert",
     320, "german chocolate dessert cake"),

    (12, "Профитроли", "Профитроли", "Profiteroles",
     "Заварные пирожные с кремом и шоколадной глазурью",
     "Кремдин жана шоколад глазурьдун менен заварной пирожное",
     "Choux pastry with cream and chocolate glaze",
     280, "profiteroles chocolate cream pastry"),

    (12, "Наполеон", "Наполеон", "Napoleon Cake",
     "Классический многослойный торт Наполеон с кремом",
     "Кремдин менен классикалык көп катмарлуу наполеон торт",
     "Classic multi-layer Napoleon cake with cream",
     320, "napoleon cake layers cream classic"),

    (12, "Дубайский Чизкейк", "Дубай Чизкейк", "Dubai Cheesecake",
     "Чизкейк в дубайском стиле с шоколадом и фисташками",
     "Шоколад жана мисте менен дубайлык стилдеги чизкейк",
     "Dubai-style cheesecake with chocolate and pistachios",
     280, "dubai cheesecake chocolate pistachio"),

    (12, "Чиа Пудинг Манго Маракуйя", "Чиа Пудинг Манго Маракуйя", "Chia Pudding Mango Passion Fruit",
     "Чиа пудинг с манго и маракуйей",
     "Манго жана маракуйя менен чиа пудинг",
     "Chia pudding with mango and passion fruit",
     220, "chia pudding mango passion fruit"),

    (12, "Пудинг Фисташка Шоколад", "Пудинг Мисте Шоколад", "Pistachio Chocolate Pudding",
     "Нежный пудинг с фисташками и шоколадом",
     "Мисте жана шоколад менен назик пудинг",
     "Delicate pudding with pistachios and chocolate",
     220, "pistachio chocolate pudding"),

    (12, "Пудинг Клубничный", "Пудинг Кулпунай", "Strawberry Pudding",
     "Нежный клубничный пудинг",
     "Назик кулпунай пудинги",
     "Delicate strawberry pudding",
     220, "strawberry pudding creamy"),

    (12, "Трюфельный Торт", "Трюфель Торт", "Truffle Cake",
     "Шоколадный торт с трюфельным кремом",
     "Трюфель крем менен шоколад торт",
     "Chocolate cake with truffle cream",
     350, "truffle chocolate cake dark"),

    (12, "Черносмородиновый Чизкейк", "Кара Карагат Чизкейк", "Black Currant Cheesecake",
     "Чизкейк с черной смородиной",
     "Кара карагат менен чизкейк",
     "Cheesecake with black currant",
     350, "blackcurrant cheesecake purple"),

    (12, "Шоколадный Флан", "Шоколад Флан", "Chocolate Flan",
     "Нежный шоколадный флан с карамелью",
     "Карамель менен назик шоколад флан",
     "Delicate chocolate flan with caramel",
     280, "chocolate flan caramel custard"),

    (12, "Медовик Шоколадный", "Шоколаддуу Бал Торт", "Chocolate Honey Cake",
     "Медовый торт с шоколадным кремом",
     "Шоколад крем менен бал торт",
     "Honey cake with chocolate cream",
     280, "honey cake chocolate layers medovik"),

    (12, "Медовик Классический", "Классикалык Бал Торт", "Classic Honey Cake",
     "Классический медовый торт со сметанным кремом",
     "Каймак крем менен классикалык бал торт",
     "Classic honey cake with sour cream",
     280, "classic honey cake cream medovik"),

    (12, "Эклеры", "Эклеры", "Eclairs",
     "Заварные эклеры с шоколадом, ванилью или маракуйей",
     "Шоколад, ваниль же маракуйя менен заварной эклерлер",
     "Choux eclairs with chocolate, vanilla or passion fruit",
     160, "eclairs chocolate vanilla cream pastry"),

    (12, "Мороженое", "Балмуздак", "Ice Cream",
     "Клубничное/ пломбир/ шоколадное/ манго/ бабл гам/ лесные ягоды/ вишня",
     "Кулпунай/ каймак/ шоколад/ манго/ бабл гам/ мөмө/ алча",
     "Strawberry/ vanilla/ chocolate/ mango/ bubble gum/ forest berries/ cherry",
     160, "ice cream scoop colorful"),

    (12, "Цветочный Горшок", "Гул Идиш", "Flower Pot Dessert",
     "Оригинальный десерт в виде цветочного горшка",
     "Гул идиши түрүндөгү оригиналдуу десерт",
     "Original dessert shaped like a flower pot",
     320, "flower pot dessert oreo cream chocolate"),

    (12, "Десерт Груша", "Десерт Алмурут", "Pear Dessert",
     "Изысканный десерт с грушей и мороженым",
     "Алмурут жана балмуздак менен назик десерт",
     "Elegant dessert with pear and ice cream",
     320, "pear poached dessert ice cream"),

    # ── ЧАИ (13) ───────────────────────────────────────────────────────────────
    (13, "Чай Черный/Зеленый", "Кара/Көк Чай", "Black/Green Tea",
     "Черный или зеленый чай",
     "Кара же көк чай",
     "Black or green tea",
     60, "black green tea cup"),

    (13, "Чай Дольче Вита", "Дольче Вита Чайы", "Dolce Vita Tea",
     "Чай каркаде, базилик, апельсин, фирменный соус",
     "Каркаде чайы, райхан, апельсин, өзгөчө соус",
     "Hibiscus tea, basil, orange, signature sauce",
     290, "hibiscus tea orange basil"),

    (13, "Чай Имбирный", "Имбирь Чайы", "Ginger Tea",
     "Имбирь, лимон, мед, зеленый чай",
     "Имбирь, лимон, бал, көк чай",
     "Ginger, lemon, honey, green tea",
     290, "ginger lemon honey tea"),

    (13, "Чай Барбарисовый", "Бөру Карагат Чайы", "Barberry Tea",
     "Барбарис, яблоко, апельсин, карамельный сироп, мед",
     "Бөру карагат, алма, апельсин, карамель ширеси, бал",
     "Barberry, apple, orange, caramel syrup, honey",
     290, "barberry apple tea warm"),

    (13, "Чай Мята-Маракуйя", "Жалбыз-Маракуйя Чайы", "Mint-Passion Fruit Tea",
     "Апельсин, сироп маракуйя, мята, черный чай",
     "Апельсин, маракуйя ширеси, жалбыз, кара чай",
     "Orange, passion fruit syrup, mint, black tea",
     290, "mint passion fruit tea warm"),

    (13, "Чай Малина-Маракуйя", "Малина-Маракуйя Чайы", "Raspberry Passion Fruit Tea",
     "Апельсин, малина, мята, сироп маракуйя, черный чай",
     "Апельсин, дан куурай, жалбыз, маракуйя ширеси, карай чай",
     "Orange, raspberry, mint, passion fruit syrup, black tea",
     290, "raspberry passion fruit tea"),

    (13, "Чай Цитрусовый", "Цитрус Чайы", "Citrus Tea",
     "Апельсин, лимон, сахарный сироп, мята",
     "Апельсин, лимон, шекер ширеси, жалбыз",
     "Orange, lemon, sugar syrup, mint",
     290, "citrus tea orange lemon warm"),

    (13, "Чай Шиповник", "Ит Мурун Чайы", "Rosehip Tea",
     "Шиповник, апельсин, мед, мята",
     "Ит мурун, апельсин, бал, жалбыз",
     "Rosehip, orange, honey, mint",
     290, "rosehip tea orange honey"),

    (13, "Чай Облепиховый", "Чычырканак Чайы", "Sea Buckthorn Tea",
     "Облепиха, мед, лимон",
     "Чычырканак, бал, лимон",
     "Sea buckthorn, honey, lemon",
     290, "sea buckthorn tea orange"),

    (13, "Яблочный с Корицей", "Алма Менен Корица", "Apple Cinnamon Tea",
     "Травяной чай, яблоко, корица",
     "Чөп чай, алма, корица",
     "Herbal tea, apple, cinnamon",
     290, "apple cinnamon tea warm"),

    # ── НАПИТКИ (14) ───────────────────────────────────────────────────────────
    (14, "Coca-Cola", "Кока-Кола", "Coca-Cola",
     "Газированный напиток Coca-Cola 0.25л / 1л",
     "Газдалган суусундук Coca-Cola 0.25л / 1л",
     "Coca-Cola sparkling drink 0.25L / 1L",
     170, "coca cola bottle can"),

    (14, "Fanta", "Фанта", "Fanta",
     "Газированный напиток Fanta 0.25л / 1л",
     "Газдалган суусундук Фанта 0.25л / 1л",
     "Fanta sparkling drink 0.25L / 1L",
     170, "fanta orange drink bottle"),

    (14, "Sprite", "Спрайт", "Sprite",
     "Газированный напиток Sprite",
     "Газдалган суусундук Спрайт",
     "Sprite sparkling drink",
     170, "sprite lemon lime drink"),

    (14, "Bonaqua", "Боноква", "Bonaqua",
     "Минеральная вода Bonaqua",
     "Минерал суу Боноква",
     "Bonaqua mineral water",
     90, "bonaqua water bottle mineral"),

    (14, "Schweppes", "Швепс", "Schweppes",
     "Газированный напиток Schweppes",
     "Газдалган суусундук Швепс",
     "Schweppes sparkling drink",
     160, "schweppes tonic drink bottle"),

    (14, "Боржоми", "Боржоми", "Borjomi",
     "Минеральная вода Боржоми",
     "Минерал суу Боржоми",
     "Borjomi mineral water",
     190, "borjomi mineral water georgia"),

    (14, "Соки в Ассортименте", "Ширелер Ассортиси", "Juice Assortment",
     "Соки различных вкусов на выбор",
     "Ар кандай даам ширелери",
     "Various flavor juices",
     290, "juice assortment fruit"),

    # ── СМУЗИ (15) ─────────────────────────────────────────────────────────────
    (15, "Смузи Клубничный", "Кулпунай Смузи", "Strawberry Smoothie",
     "Клубника, банан, сок вишня, сироп клубничный, мед",
     "Кулпунай, банан, алча ширеси, кулпунай ширеси, бал",
     "Strawberry, banana, cherry juice, strawberry syrup, honey",
     290, "strawberry smoothie pink banana"),

    (15, "Смузи Банановый", "Банан Смузи", "Banana Smoothie",
     "Банан, сок ананасовый, сироп банановый, мед",
     "Банан, ананас ширеси, банан ширеси, бал",
     "Banana, pineapple juice, banana syrup, honey",
     290, "banana smoothie yellow creamy"),

    (15, "Смузи Малиновый", "Малина Смузи", "Raspberry Smoothie",
     "Малина, банан, сок апельсиновый, сироп гранатовый, мед",
     "Дан куурай, банан, апельсин ширеси, анар ширеси, бал",
     "Raspberry, banana, orange juice, pomegranate syrup, honey",
     290, "raspberry smoothie red berry"),

    (15, "Смузи Остров Киви", "Киви Аралы Смузи", "Kiwi Island Smoothie",
     "Киви, банан, сок яблочный, сироп киви, мед",
     "Киви, банан, алма ширеси, киви ширеси, бал",
     "Kiwi, banana, apple juice, kiwi syrup, honey",
     290, "kiwi smoothie green fresh"),

    # ── КОФЕ (16) ──────────────────────────────────────────────────────────────
    (16, "Американо", "Американо", "Americano",
     "Эспрессо с горячей водой",
     "Ысык суу менен эспрессо",
     "Espresso with hot water",
     140, "americano coffee black"),

    (16, "Двойной Американо", "Кош Американо", "Double Americano",
     "Двойной эспрессо с горячей водой",
     "Кош эспрессо ысык суу менен",
     "Double espresso with hot water",
     180, "double americano coffee"),

    (16, "Капучино", "Капучино", "Cappuccino",
     "Эспрессо, взбитое молоко, молочная пена",
     "Эспрессо, жутулган сүт, сүт көбүгү",
     "Espresso, steamed milk, milk foam",
     190, "cappuccino coffee foam milk"),

    (16, "Капучино с Халвой", "Халва Менен Капучино", "Cappuccino with Halva",
     "Капучино с добавлением халвы",
     "Халва кошулган капучино",
     "Cappuccino with halva",
     240, "cappuccino halva special coffee"),

    (16, "Бамбл Кофе", "Бамбл Кофе", "Bumble Coffee",
     "Холодный кофе с апельсиновым соком и мёдом",
     "Апельсин ширеси жана бал менен муздак кофе",
     "Cold coffee with orange juice and honey",
     320, "bumble coffee orange honey cold"),

    (16, "Флэт Уайт", "Флэт Уайт", "Flat White",
     "Двойной эспрессо с бархатистым молоком",
     "Кош эспрессо бархаттай сүт менен",
     "Double espresso with velvety milk",
     240, "flat white coffee milk"),

    (16, "Эспрессо", "Эспрессо", "Espresso",
     "Классический итальянский кофе эспрессо",
     "Классикалык итальялык эспрессо кофе",
     "Classic Italian espresso coffee",
     140, "espresso coffee shot"),

    (16, "Латте", "Латте", "Latte",
     "Эспрессо с большим количеством взбитого молока",
     "Эспрессо көп жутулган сүт менен",
     "Espresso with a large amount of steamed milk",
     190, "latte coffee milk"),

    (16, "Мокко", "Мокко", "Mocha",
     "Эспрессо, шоколад, молоко",
     "Эспрессо, шоколад, сүт",
     "Espresso, chocolate, milk",
     220, "mocha coffee chocolate milk"),

    (16, "Раф Кофе", "Раф Кофе", "Raf Coffee",
     "Кофе с ванильным сахаром и сливками",
     "Ваниль шекер жана каймак менен кофе",
     "Coffee with vanilla sugar and cream",
     260, "raf coffee vanilla cream"),

    (16, "Раф Баунти", "Раф Баунти", "Bounty Raf",
     "Раф кофе со вкусом кокоса и шоколада",
     "Кокос жана шоколад даамы менен раф кофе",
     "Raf coffee with coconut and chocolate flavor",
     280, "bounty raf coffee coconut chocolate"),

    (16, "Глясе", "Глясе", "Coffee Glase",
     "Кофе с мороженым",
     "Балмуздак менен кофе",
     "Coffee with ice cream",
     220, "coffee glace ice cream"),

    (16, "Аффогато", "Аффогато", "Affogato",
     "Шарик мороженого с горячим эспрессо",
     "Ысык эспрессо менен балмуздак",
     "Ice cream scoop with hot espresso",
     280, "affogato espresso ice cream"),

    (16, "Матча Латте", "Матча Латте", "Matcha Latte",
     "Латте из японского зеленого чая матча",
     "Жапон жашыл чай матчадан жасалган латте",
     "Latte made from Japanese matcha green tea",
     140, "matcha latte green tea"),

    (16, "Айс Латте", "Айс Латте", "Iced Latte",
     "Холодный латте со льдом",
     "Муз менен муздак латте",
     "Cold latte with ice",
     200, "iced latte coffee cold"),

    (16, "Какао с Маршмеллоу", "Какао Зефир Менен", "Hot Chocolate with Marshmallow",
     "Горячее какао с маршмеллоу",
     "Маршмеллоу менен ысык какао",
     "Hot cocoa with marshmallow",
     220, "hot chocolate marshmallow cocoa"),

    # ── ЛИМОНАДЫ (17) ──────────────────────────────────────────────────────────
    (17, "Лимонад Клубничный", "Кулпунай Лимонады", "Strawberry Lemonade",
     "Апельсин, сироп клубничный, лимонный сироп, мята",
     "Апельсин, кулпунай ширеси, лимон ширеси, жалбыз",
     "Orange, strawberry syrup, lemon syrup, mint",
     340, "strawberry lemonade pink mint"),

    (17, "Лимонад Мохито", "Мохито Лимонады", "Mojito Lemonade",
     "Лайм, сироп мохито, лимонный сироп, мята",
     "Лайм, мохито ширеси, лимон ширеси, жалбыз",
     "Lime, mojito syrup, lemon syrup, mint",
     340, "mojito lemonade lime mint"),

    (17, "Лимонад Маракуйя", "Маракуйя Лимонады", "Passion Fruit Lemonade",
     "Апельсин, сироп маракуйя, лимонный сироп, мята",
     "Апельсин, маракуйя ширеси, лимон ширеси, жалбыз",
     "Orange, passion fruit syrup, lemon syrup, mint",
     340, "passion fruit lemonade orange"),

    (17, "Лимонад Малиновый", "Малина Лимонады", "Raspberry Lemonade",
     "Апельсин, сироп малиновый, пюре, лимонный сироп, мята",
     "Апельсин, малина ширеси, пюре, лимон ширеси, жалбыз",
     "Orange, raspberry syrup, purée, lemon syrup, mint",
     340, "raspberry lemonade red pink"),

    (17, "Лимонад Тархун", "Тархун Лимонады", "Tarragon Lemonade",
     "Апельсин, сироп тархун, лимонный сироп, мята",
     "Апельсин, тархун ширеси, лимон ширеси, жалбыз",
     "Orange, tarragon syrup, lemon syrup, mint",
     340, "tarragon lemonade green"),

    (17, "Лимонад Лесные Ягоды", "Токой Мөмөлөрү Лимонады", "Forest Berry Lemonade",
     "Апельсин, сироп лесных ягод, лимонный сироп, мята",
     "Апельсин, токой мөмөлөрүнүн ширеси, лимон ширеси, жалбыз",
     "Orange, forest berry syrup, lemon syrup, mint",
     340, "forest berry lemonade purple"),

    (17, "Лимонад Арбузный", "Дарбуз Лимонады", "Watermelon Lemonade",
     "Апельсин, сироп арбузный, лимонный сироп, мята",
     "Апельсин, дарбыз ширеси, лимон ширеси, жалбыз",
     "Orange, watermelon syrup, lemon syrup, mint",
     340, "watermelon lemonade pink summer"),

    (17, "Лимонад Цитрусовый", "Цитрус Лимонады", "Citrus Lemonade",
     "Апельсин, лайм, лимон, сироп сахарный, лимонный сироп, мята",
     "Апельсин, лайм, лимон, шекер ширеси, лимон ширеси, жалбыз",
     "Orange, lime, lemon, sugar syrup, lemon syrup, mint",
     340, "citrus lemonade yellow lime"),

    (17, "Лимонад Малина-Маракуйя", "Малина-Маракуйя Лимонады", "Raspberry Passion Fruit Lemonade",
     "Апельсин, сироп малиновый, сироп маракуйя, лимонный сироп, мята",
     "Апельсин, малина ширеси, маракуйя ширеси, лимон ширеси, жалбыз",
     "Orange, raspberry syrup, passion fruit syrup, lemon syrup, mint",
     340, "raspberry passion fruit lemonade"),

    (17, "Айс-Ти Чай", "Муздатылган Чай Лимонады", "Iced Tea Lemonade",
     "Чай черный/зеленый, лимон, мята, сахарный сироп",
     "Кара/көк чай, лимон, жалбыз, шекер ширеси",
     "Black/green tea, lemon, mint, sugar syrup",
     340, "iced tea lemonade cold"),

    # ── КОКТЕЙЛИ (18) ──────────────────────────────────────────────────────────
    (18, "Коктейль Классический", "Классикалык Коктейль", "Classic Milkshake",
     "Пломбир, сливки, молоко, пюре, взбитые сливки",
     "Балмуздак, каймак, сүт, пюре, камкайман",
     "Vanilla ice cream, cream, milk, purée, whipped cream",
     320, "classic milkshake vanilla cream"),

    (18, "Коктейль Лесные Ягоды", "Токой Мөмөлөрү Коктейли", "Forest Berry Milkshake",
     "Мороженое лесные ягоды, сливки, молоко, пюре, взбитые сливки",
     "Токой мөмөлөрү менен балмуздак, каймак, сүт, пюре, камкайман",
     "Forest berry ice cream, cream, milk, purée, whipped cream",
     320, "forest berry milkshake purple"),

    (18, "Коктейль Клубничный", "Кулпунай Коктейли", "Strawberry Milkshake",
     "Клубничное мороженое, сливки, молоко, пюре, взбитые сливки",
     "Кулпунай балмуздагы, каймак, сүт, пюре, камкайман",
     "Strawberry ice cream, cream, milk, purée, whipped cream",
     320, "strawberry milkshake pink cream"),

    (18, "Коктейль Банановый", "Банан Коктейли", "Banana Milkshake",
     "Банановое мороженое, сливки, молоко, пюре, взбитые сливки",
     "Банан балмуздагы, каймак, сүт, пюре, камкайман",
     "Banana ice cream, cream, milk, purée, whipped cream",
     320, "banana milkshake yellow cream"),

    (18, "Коктейль Шоколадный", "Шоколад Коктейли", "Chocolate Milkshake",
     "Шоколадное мороженое, сливки, молоко, пюре, взбитые сливки",
     "Шоколад балмуздагы, каймак, сүт, пюре, камкайман",
     "Chocolate ice cream, cream, milk, purée, whipped cream",
     320, "chocolate milkshake dark brown"),

    (18, "Коктейль Пеликан", "Пеликан Коктейли", "Pelican Cocktail",
     "Банан, сок персиковый, гранатовый сироп",
     "Банан, шабдаалы ширеси, анар ширеси",
     "Banana, peach juice, pomegranate syrup",
     320, "pelican cocktail tropical fruit"),

    (18, "Банано-Кокосовое Наслаждение", "Банан-Кокос Ырахаты", "Banana Coconut Delight",
     "Банан, сливки, кокосовый сироп, ананасовый сок",
     "Банан, каймак, кокос ширеси, ананас ширеси",
     "Banana, cream, coconut syrup, pineapple juice",
     320, "banana coconut milkshake tropical"),
]


def _compress_image(image_data, filename, max_side=800, quality=78):
    """Resize and convert to WebP."""
    from io import BytesIO
    from PIL import Image
    from django.core.files.base import ContentFile
    try:
        img = Image.open(BytesIO(image_data)).convert("RGB")
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, "WEBP", quality=quality, method=6)
        buf.seek(0)
        base = os.path.splitext(filename)[0]
        return ContentFile(buf.read()), f"{base}.webp"
    except Exception as e:
        return None, str(e)


def _download_image(query, item_slug, stdout, pexels_key=None):
    """Download a food image. Tries Pexels API first, then DuckDuckGo."""
    import requests

    # ── 1. Pexels API (reliable, free key at pexels.com/api) ─────────────────
    if pexels_key:
        try:
            r = requests.get(
                "https://api.pexels.com/v1/search",
                params={"query": query + " food", "per_page": 5, "orientation": "square"},
                headers={"Authorization": pexels_key},
                timeout=15,
            )
            if r.status_code == 200:
                for photo in r.json().get("photos", []):
                    img_url = (photo.get("src") or {}).get("large") or (photo.get("src") or {}).get("medium")
                    if not img_url:
                        continue
                    try:
                        resp = requests.get(img_url, timeout=20)
                        if resp.status_code == 200 and len(resp.content) > 8000:
                            content, fname = _compress_image(resp.content, f"{item_slug}.jpg")
                            if content:
                                return content, fname
                    except Exception:
                        continue
            else:
                stdout.write(f"      Pexels HTTP {r.status_code}")
        except Exception as e:
            stdout.write(f"      Pexels error: {e}")

    # ── 2. DuckDuckGo fallback ────────────────────────────────────────────────
    import re
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://duckduckgo.com/",
    }
    try:
        r = requests.get(
            "https://duckduckgo.com/",
            params={"q": query + " food dish"},
            headers=headers,
            timeout=10,
        )
        vqd_match = re.search(r'vqd=([\d-]+)', r.text)
        if vqd_match:
            r2 = requests.get(
                "https://duckduckgo.com/i.js",
                params={"q": query + " food", "o": "json", "vqd": vqd_match.group(1), "f": ",,,", "p": "1"},
                headers=headers,
                timeout=10,
            )
            for result in r2.json().get("results", [])[:5]:
                img_url = result.get("image")
                if not img_url:
                    continue
                try:
                    resp = requests.get(img_url, timeout=12, headers=headers)
                    if resp.status_code == 200 and len(resp.content) > 8000:
                        content, fname = _compress_image(resp.content, f"{item_slug}.jpg")
                        if content:
                            return content, fname
                except Exception:
                    continue
    except Exception as e:
        stdout.write(f"      DDG error: {e}")

    return None, None


class Command(BaseCommand):
    help = "Import Dolce Vita Family restaurant with full menu from DOLCE MENU 2026.pdf"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Parse only, do NOT write to DB")
        parser.add_argument("--no-images", action="store_true",
                            help="Skip image downloads")
        parser.add_argument("--reset", action="store_true",
                            help="Delete existing Dolce Vita restaurant and reimport")
        parser.add_argument("--pexels-key", default="",
                            help="Free Pexels API key for images (get at pexels.com/api)")

    def log(self, msg):
        self.stdout.write(msg)

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def err(self, msg):
        self.stdout.write(self.style.ERROR(msg))

    def handle(self, *args, **options):
        dry = options["dry_run"]
        no_img = options["no_images"]
        reset = options["reset"]
        pexels_key = options.get("pexels_key", "").strip()

        img_source = "skip" if no_img else ("Pexels API" if pexels_key else "DuckDuckGo (try --pexels-key for reliability)")
        self.log(f"🍽  Dolce Vita Family menu import")
        self.log(f"   Categories : {len(CATEGORIES)}")
        self.log(f"   Items      : {len(ITEMS)}")
        self.log(f"   Dry run    : {dry}")
        self.log(f"   Images     : {img_source}")

        if dry:
            for i, (name_ru, name_ky, name_en) in enumerate(CATEGORIES):
                self.log(f"  [{i}] {name_ru}")
            for row in ITEMS:
                cat_idx, name_ru = row[0], row[1]
                price = row[7]
                self.log(f"     [{cat_idx}] {name_ru} — {price} сом")
            self.ok(f"\n✅ DRY RUN complete — {len(ITEMS)} items listed, no DB writes.")
            return

        from catalog.models import (
            BranchCategory, BranchCategoryItem, BranchItem,
            BranchMenuSet, Category, Item, ItemCategory, MenuSet,
        )
        from core.models import Branch, Restaurant

        # ── Reset ────────────────────────────────────────────────────────────
        if reset:
            deleted = Restaurant.objects.filter(slug=RESTAURANT["slug"]).delete()
            self.log(f"   🗑  Deleted: {deleted}")

        # ── Restaurant ───────────────────────────────────────────────────────
        restaurant, created = Restaurant.objects.get_or_create(
            slug=RESTAURANT["slug"],
            defaults={
                "name_ru": RESTAURANT["name_ru"],
                "name_ky": RESTAURANT["name_ky"],
                "name_en": RESTAURANT["name_en"],
                "about_ru": RESTAURANT["about_ru"],
                "about_ky": RESTAURANT["about_ky"],
                "about_en": RESTAURANT["about_en"],
                "is_active": True,
            },
        )
        self.ok(f"\n{'✨ Created' if created else '♻️  Found'} Restaurant id={restaurant.id} '{restaurant.name_ru}'")

        # ── Branch ───────────────────────────────────────────────────────────
        branch, _ = Branch.objects.get_or_create(
            restaurant=restaurant,
            name_ru=BRANCH["name_ru"],
            defaults={
                "name_ky": BRANCH["name_ky"],
                "name_en": BRANCH["name_en"],
                "is_active": True,
                "is_open_24h": BRANCH["is_open_24h"],
                "work_days": BRANCH["work_days"],
            },
        )
        self.log(f"   Branch id={branch.id}")

        # ── MenuSet ──────────────────────────────────────────────────────────
        menu_set, _ = MenuSet.objects.get_or_create(
            restaurant=restaurant,
            name="Основное меню",
            defaults={"is_active": True},
        )
        BranchMenuSet.objects.get_or_create(branch=branch, menu_set=menu_set)
        self.log(f"   MenuSet id={menu_set.id}")

        # ── Categories ───────────────────────────────────────────────────────
        self.log(f"\n📂 Creating {len(CATEGORIES)} categories...")
        cat_objects = []
        bc_objects = []
        for i, (name_ru, name_ky, name_en) in enumerate(CATEGORIES):
            cat, _ = Category.objects.get_or_create(
                menu_set=menu_set,
                name_ru=name_ru,
                defaults={"name_ky": name_ky, "name_en": name_en},
            )
            bc, _ = BranchCategory.objects.get_or_create(
                branch=branch,
                category=cat,
                defaults={"sort_order": i * 10, "is_active": True},
            )
            cat_objects.append(cat)
            bc_objects.append(bc)
            self.log(f"   [{i}] {name_ru}")
        self.ok(f"   ✅ {len(cat_objects)} categories ready")

        # ── Items ────────────────────────────────────────────────────────────
        self.log(f"\n🍽  Creating {len(ITEMS)} items...")
        created_count = 0
        img_ok = 0
        img_fail = 0

        for idx, row in enumerate(ITEMS):
            cat_idx, name_ru, name_ky, name_en, desc_ru, desc_ky, desc_en, price, img_query = row

            price_dec = Decimal(str(price)) if price else Decimal("0")

            item, item_new = Item.objects.get_or_create(
                restaurant=restaurant,
                name_ru=name_ru,
                defaults={
                    "name_ky": name_ky,
                    "name_en": name_en,
                    "description_ru": desc_ru,
                    "description_ky": desc_ky,
                    "description_en": desc_en,
                    "base_price": price_dec,
                },
            )
            if not item_new:
                # Update multilingual fields on existing items
                updated = False
                for field, val in [
                    ("name_ky", name_ky), ("name_en", name_en),
                    ("description_ru", desc_ru), ("description_ky", desc_ky),
                    ("description_en", desc_en),
                ]:
                    if not getattr(item, field):
                        setattr(item, field, val)
                        updated = True
                if price_dec and not item.base_price:
                    item.base_price = price_dec
                    updated = True
                if updated:
                    item.save()

            # Image
            if not item.photo and not no_img and img_query:
                from django.utils.text import slugify
                slug = slugify(name_en or name_ru)[:40]
                content, fname = _download_image(img_query, slug, self.stdout, pexels_key=pexels_key)
                if content:
                    item.photo.save(fname, content, save=True)
                    img_ok += 1
                    self.log(f"   [{idx+1}/{len(ITEMS)}] 🖼  {name_ru} — image saved")
                else:
                    img_fail += 1
                    self.log(f"   [{idx+1}/{len(ITEMS)}] ⚠  {name_ru} — no image")
            else:
                self.log(f"   [{idx+1}/{len(ITEMS)}] {'✨' if item_new else '♻'} {name_ru} — {price_dec} сом")

            # BranchItem
            bi, _ = BranchItem.objects.get_or_create(
                branch=branch,
                item=item,
                defaults={"price": price_dec, "is_available": True},
            )

            # ItemCategory → Category link
            cat = cat_objects[cat_idx]
            item_cat, _ = ItemCategory.objects.get_or_create(
                item=item,
                category=cat,
                defaults={"sort_order": idx},
            )

            # BranchCategoryItem → BranchCategory link
            bc = bc_objects[cat_idx]
            BranchCategoryItem.objects.get_or_create(
                branch_category=bc,
                branch_item=bi,
                defaults={"sort_order": idx},
            )

            if item_new:
                created_count += 1

        self.ok(f"\n✅ Done!")
        self.ok(f"   Items created : {created_count}")
        self.ok(f"   Items found   : {len(ITEMS) - created_count}")
        if not no_img:
            self.ok(f"   Images OK     : {img_ok}")
            self.ok(f"   Images failed : {img_fail}")
        self.ok(f"\n🔗 Restaurant slug: {RESTAURANT['slug']}")
        self.ok(f"   Run again with --no-images to skip image downloads.")
        self.ok(f"   Run again with --reset to delete and reimport from scratch.")
