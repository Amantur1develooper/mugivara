"""
Создаёт ресторан «Булак Sport Community» + филиал + полное меню (RU/KY/EN),
собранное с реального PDF-меню заведения (28 страниц: каши, завтраки, закуски,
покэ, салаты, снеки, пицца, паста, супы, гриль, мясо/курица, овощи/гарниры,
выпечка, детское меню, кофе, bubble tea, лимонады, чаи, коктейли, соки, напитки,
добавки, спортивное питание).

Это ОТДЕЛЬНЫЙ ресторан от уже существующего в базе "Булак" (slug=bulak,
импортирован из Excel) — slug здесь по умолчанию "bulak-2", чтобы не столкнуться
со старой записью.

Фото категорий — кадры, вырезанные напрямую из фотографий на страницах самого
PDF-меню (реальная предметная съёмка заведения), лежат рядом с этой командой в
папке _bulak2_menu_photos/ — интернет при запуске не нужен. В PDF на большинство
позиций одна общая фотография на категорию/группу блюд (а не фото на каждую
позицию отдельно) — поэтому позиции внутри категории используют один и тот же
файл фото.

Пищевая ценность (калории/белки/жиры/углеводы), где она указана в PDF, записана
в отдельные поля Item (calories/protein/fat/carbs) и отображается на карточке
блюда бейджами.

Использование:
    python manage.py create_bulak2_menu
    python manage.py create_bulak2_menu --slug "bulak-2" --address "г. Бишкек, ..." --phone "+996 555 88 66 36"
    python manage.py create_bulak2_menu --dry-run
"""

import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "_bulak2_menu_photos")

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


def mk(name_ru, name_ky, name_en, price, desc_ru="", desc_ky="", desc_en="",
       k=None, b=None, j=None, u=None, photo=None):
    """КБЖУ (k=калории, b=белки, j=жиры, u=углеводы) идут в отдельные поля Item,
    а не в текст описания."""
    return (name_ru, name_ky, name_en, price, desc_ru, desc_ky, desc_en, photo, k, b, j, u)


# ── Меню: (категория_ru, категория_ky, категория_en, [items]) ──────────────
# item = (name_ru, name_ky, name_en, price, desc_ru, desc_ky, desc_en, photo_key)
MENU_DATA = [
    ("Каши", "Ботколор", "Porridges", [
        mk("Каша овсянная", "Сулу боткосу", "Oatmeal Porridge", 200,
           k=110, b=3, j=4.5, u=15, photo="cat-kashi.jpg"),
        mk("Каша рисовая", "Күрүч боткосу", "Rice Porridge", 200,
           k=115, b=2.8, j=4.6, u=16, photo="cat-kashi.jpg"),
        mk("Каша гречневая", "Гречка боткосу", "Buckwheat Porridge", 200,
           k=125, b=4.3, j=5.1, u=16.5, photo="cat-kashi.jpg"),
    ]),

    ("Сладкие завтраки", "Таттуу эртең мененки тамактар", "Sweet Breakfasts", [
        mk("Сырники с бананом и клубникой", "Банан жана кулпунай кошулган сырниктер", "Cheese Pancakes with Banana & Strawberry", 300,
           "Нежнейшие сырники из натурального творог с добавлением сладкой сгущенкой",
           "Табигый быштактан даярдалган жумшак сырниктер, таттуу коюлтулган сүт кошулуп жасалат.",
           "Delicate cheese pancakes made from natural cottage cheese with sweet condensed milk.",
           k=558, b=28, j=18, u=45, photo="item-syrniki-banan-klubnika.jpg"),
        mk("Гранола", "Гранола", "Granola", 300,
           "Питательный завтрак из смеси полезных злаков, орехов и фруктов подается с натуральным йогуртом",
           "Дан азыктарынын, жаңгактардын жана мөмө-жемиштердин пайдалуу аралашмасынан даярдалган аш болумдуу эртең мененки тамак. Табигый йогурт менен берилет.",
           "A hearty breakfast of grains, nuts and fruit, served with natural yogurt.",
           k=420, b=16, j=20, u=55, photo="stock-granola.jpg"),
        mk("Блины с творогом", "Быштак салынган блинчиктер", "Pancakes with Cottage Cheese", 250,
           k=675, b=27, j=29, u=76, photo="stock-blini-tvorog.jpg"),
        mk("Блины классические со сметаной", "Классикалык блинчиктер каймак менен", "Classic Pancakes with Sour Cream", 250,
           photo="stock-blini-smetana.jpg"),
        mk("Творожный боул с ягодами по сезону", "Мезгилдик мөмө-жемиштер кошулган быштак боулу", "Cottage Cheese Bowl with Seasonal Berries", 300,
           k=395, b=12, j=18, u=47, photo="item-tvorog-boul-yagody.jpg"),
    ]),

    ("Сытные завтраки мировые", "Дүйнө ашканасынан тойгузуучу эртең мененки тамактар", "Hearty World Breakfasts", [
        mk("Фирменный завтрак", "Фирмалык эртең мененки тамак", "Signature Breakfast", 550,
           "багет, хрустящая курица, фирменные колбаски, кукуруза консервированная, микс салат, яичница болтунья",
           "Багет, кытырак тоок эти, фирмалык колбасалар, консерваланган жүгөрү, салат аралашмасы жана болтунья жумуртка.",
           "Baguette, crispy chicken, signature sausages, canned corn, mixed salad and scrambled eggs.",
           k=180, b=9, j=11, u=12, photo="item-firmenny-zavtrak.jpg"),
        mk("Турецкий завтрак", "Түрк эрте мененки тамагы", "Turkish Breakfast", 425,
           "свежие овощи, фрукты, орехи, джем, мед, масло, хлеб, симмит",
           "Свежие овощи, фрукты, орехи, джем, мед, май, нан, симит.",
           "Fresh vegetables, fruit, nuts, jam, honey, butter, bread, simit bread.",
           k=544, b=14, j=31, u=52, photo="stock-turkish-breakfast.jpg"),
        mk("Крок Мадам", "Крок Мадам", "Croque Madame", 350,
           "Классический французский сендвич с запеченной говядиной, сыром и соусом Бешамель и глазуньей. Подается с микс салатом",
           "Куурулган уй эти, сыр, «Бешамель» соусу жана көз жумуртка кошулган классикалык француз сэндвичи. Салат аралашмасы менен берилет.",
           "Classic French sandwich with baked beef, cheese, béchamel sauce and a fried egg. Served with mixed salad.",
           k=355, b=17, j=21, u=25, photo="item-krok-madam.jpg"),
        mk("Бенедикт с форелью", "Форель кошулган Бенедикт", "Trout Benedict", 450,
           "брускетты со слабосоленой форелью и яйцом пашот, залитый с соусом Голландез, микс салата с вяленными томатами",
           "Женил туздалган форель жана пашот жумурткасы кошулган брускетталар, «Голландез» соусу куюлуп, какталган помидор кошулган салат аралашмасы менен берилет.",
           "Bruschetta with lightly salted trout and poached egg, topped with Hollandaise sauce, served with mixed salad and sun-dried tomatoes.",
           k=510, b=25, j=34, u=21, photo="stock-benedict-forel.jpg"),
        mk("Национальный завтрак", "Улуттук эрте мененки тамак", "National Breakfast", 400,
           "май токоч, сары май, мед, сметана, чучук, сыр, свежие овощи",
           "Май токоч, сары май, бал, каймак, чучук, сыр жана жаңы жашылчалар.",
           "Fried bread, butter, honey, sour cream, chuchuk sausage, cheese, fresh vegetables.",
           k=1174, b=37, j=90, u=47, photo="item-natsionalny-zavtrak.jpg"),
    ]),

    ("Полезные завтраки", "Пайдалуу эртең мененки тамактар", "Healthy Breakfasts", [
        mk("Оладьи из кабачков с форелью", "Форель кошулган кабачки оладьилери", "Zucchini Pancakes with Trout", 400,
           "хлопья, кабачки, семга, творожный сыр, яйцо, микрозелень",
           "Сулу үлпөттөрү, кабачки, семга, быштак сыры, жумуртка жана микрожашылчалар.",
           "Oat flakes, zucchini, salmon, cream cheese, egg, microgreens.",
           k=395, b=22, j=24, u=22, photo="item-oladi-forel.jpg"),
        mk("Омлет с сыром и помидором", "Сыр жана помидор кошулган омлет", "Omelette with Cheese & Tomato", 200,
           k=345, b=18, j=27, u=4, photo="stock-omlet.jpg"),
        mk("Кето завтрак с форелью", "Форель кошулган кето эрте мененки тамак", "Keto Breakfast with Trout", 550,
           "яйцо пашот, форель, творожный сыр, огурцы, помидоры, огурцы, микс салатов",
           "Пашот жумурткасы, форель, быштак сыры, бадыраң, помидор жана салат аралашмасы.",
           "Poached egg, trout, cream cheese, cucumbers, tomatoes, mixed salad.",
           k=1174, b=37, j=90, u=47, photo="item-keto-forel.jpg"),
        mk("Кето завтрак с креветкой", "Креветка кошулган кето эрте мененки тамак", "Keto Breakfast with Shrimp", 550,
           "яйцо скрембл, креветки, творожный сыр, огурцы, помидоры, огурцы, микс салатов",
           "Скрэмбл жумуртка, креветка, быштак сыры, бадыраң, помидор жана салат аралашмасы.",
           "Scrambled eggs, shrimp, cream cheese, cucumbers, tomatoes, mixed salad.",
           k=475, b=24, j=39, u=7, photo="item-keto-krevetka.jpg"),
    ]),

    ("Закуски", "Жеңил закускалар", "Appetizers", [
        mk("Брускетта с форелью", "Форель кошулган брускетта", "Trout Bruschetta", 370,
           k=306, b=19, j=17, u=15, photo="item-brusketta-forel.jpg"),
        mk("Брускетта с говядиной", "Уй эти кошулган брускетта", "Beef Bruschetta", 370,
           k=520, b=28, j=26, u=45, photo="stock-brusketta-govyadina.jpg"),
        mk("Брускетта с карамелизированным луком", "Карамелдештирилген пияз кошулган брускетта", "Bruschetta with Caramelized Onion", 250,
           k=45, b=10, j=16, u=42, photo="stock-brusketta-luk.jpg"),
        mk("Брускетта Цезарь", "«Цезарь» брускеттасы", "Caesar Bruschetta", 300,
           k=234, b=15, j=14, u=14, photo="stock-brusketta-cezar.jpg"),
        mk("Битые огурцы", "Ачуу даамдагы эзилген бадыраң", "Smashed Cucumbers", 200,
           k=140, b=4, j=10, u=12, photo="item-bitye-ogurtsy.jpg"),
        mk("Овощная нарезка", "Жаңы жашылчалардын ассортиси", "Vegetable Platter", 300,
           k=100, b=3, j=0.5, u=16, photo="stock-ovoshnaya-narezka.jpg"),
        mk("Хрустящие креветки с медово горчичным соусом", "Бал-кычы соусу менен кытырак креветкалар", "Crispy Shrimp with Honey Mustard Sauce", 600,
           k=480, b=37, j=3, u=5, photo="item-hrustyashie-krevetki.jpg"),
        mk("Костный мозг с багетом и с зеленью", "Багет жана көк чөптөр менен сөөк чучугу", "Bone Marrow with Baguette & Herbs", 450,
           k=780, b=7, j=84, u=0, photo="stock-kostny-mozg.jpg"),
    ]),

    ("Покэ боул", "Покэ боул", "Poke Bowls", [
        mk("С форелью", "Форель менен", "With Trout", 500, k=350, b=20, j=18, u=25, photo="stock-poke-forel.jpg"),
        mk("С курицей", "Тоок эти менен", "With Chicken", 300, k=300, b=21, j=10, u=25, photo="stock-poke-kuritsa.jpg"),
        mk("С креветками", "Креветка менен", "With Shrimp", 500, k=350, b=20, j=15, u=37, photo="item-poke-krevetka.jpg"),
    ]),

    ("Салаты", "Салаттар", "Salads", [
        mk("Свекольный с рукколой", "Руккола кошулган кызылча салаты", "Beetroot & Arugula Salad", 250,
           k=350, b=12, j=32, u=18, photo="stock-salat-svekla-rukkola.jpg"),
        mk("Греческий", "Грек салаты", "Greek Salad", 350,
           k=294, b=9, j=24, u=11, photo="item-salat-grek.jpg"),
        mk("Шпинатный с телятиной", "Музоо эти кошулган шпинат салаты", "Spinach Salad with Veal", 400,
           k=380, b=22, j=24, u=12, photo="stock-salat-shpinat-teljatina.jpg"),
        mk("Цезарь с курицей", "Тоок эти кошулган «Цезарь» салаты", "Chicken Caesar Salad", 350,
           k=480, b=27, j=31, u=17, photo="item-salat-tsezar-kuritsa.jpg"),
        mk("Восточный", "Чыгыш салаты", "Oriental Salad", 300,
           k=360, b=22, j=21, u=18, photo="stock-salat-vostochny.jpg"),
        mk("Микс салат с форелью", "Форель кошулган салат аралашмасы", "Mixed Salad with Trout", 320,
           k=375, b=28, j=24, u=14, photo="item-mix-salat-forel.jpg"),
        mk("Салат с хрустящей моцареллой", "Кытырак моцарелла кошулган салат", "Salad with Crispy Mozzarella", 350,
           "руккола, шпинат, помидоры, моцарелла в панировке, лимонный дрессинг",
           "Руккола, шпинат, помидор, панировкадагы моцарелла жана лимон дрессинги.",
           "Arugula, spinach, tomatoes, breaded mozzarella, lemon dressing.",
           k=360, b=22, j=21, u=18, photo="stock-salat-mocarella.jpg"),
        mk("Хрустящие баклажаны", "Кытырак баклажан салаты", "Crispy Eggplant Salad", 320,
           "баклажаны, помидоры, сыр творожный, соус кисло сладкий",
           "Баклажан, помидор, быштак сыры жана таттуу-кычкыл соус.",
           "Eggplant, tomatoes, cottage cheese, sweet and sour sauce.",
           k=344, b=17, j=23, u=19, photo="item-hrustyashie-baklazhany.jpg"),
        mk('"Легкий"', "«Жеңил» салаты", '"Light" Salad', 320,
           "микс зелени, помидоры, огурцы, перец, брокколи, курица",
           "Жашыл жалбырактардын аралашмасы, помидор, бадыраң, таттуу калемпир, брокколи жана тоок эти.",
           "Mixed greens, tomatoes, cucumbers, pepper, broccoli, chicken.",
           k=200, b=28, j=14, u=12, photo="stock-salat-legky.jpg"),
        mk("Салат с рукколой и апельсином", "Руккола жана апельсин кошулган салат", "Arugula & Orange Salad", 380,
           k=320, b=10, j=24, u=28, photo="item-rukkola-apelsin.jpg"),
        mk("Салат овощной в соусе песто", "Песто соусу кошулган жашылча салаты", "Vegetable Salad with Pesto", 350,
           k=320, b=8, j=28, u=18, photo="stock-salat-pesto.jpg"),
    ]),

    ("Снеки и сендвичи", "Снэктер жана сэндвичтер", "Snacks & Sandwiches", [
        mk("Фирменный бургер с форелью", "Фирмалык форель бургери", "Signature Trout Burger", 620,
           k=620, b=65, j=49, u=72, photo="item-burger-forel.jpg"),
        mk("Бургер с курицей", "Тоок эти кошулган бургер", "Chicken Burger", 600,
           k=670, b=45, j=40, u=45, photo="stock-burger-kuritsa.jpg"),
        mk("Бургер с телятиной", "Музоо эти кошулган бургер", "Veal Burger", 600,
           k=750, b=45, j=48, u=50, photo="stock-burger-telyatina.jpg"),
        mk("Клаб сендвич с курицей гриль", "Гриль тоок эти кошулган клаб-сэндвич", "Grilled Chicken Club Sandwich", 300,
           k=980, b=42, j=55, u=90, photo="item-klab-sendvich-kuritsa-gril.jpg"),
        mk("Хрустящие куриные крылья", "Кытырак тоок канаттары", "Crispy Chicken Wings", 300,
           k=1150, b=45, j=55, u=75, photo="stock-krylya-v2.jpg"),
        mk("Кесадилья с курицей", "Тоок эти кошулган кесадилья", "Chicken Quesadilla", 350,
           k=850, b=40, j=48, u=65, photo="item-kesadilya-kuritsa.jpg"),
        mk("Кесадилья с говядиной", "Уй эти кошулган кесадилья", "Beef Quesadilla", 400,
           k=920, b=38, j=58, u=62, photo="stock-kesadilya-govyadina.jpg"),
        mk("Кесадилья 4 сыра", "Төрт сыр кошулган кесадилья", "Four Cheese Quesadilla", 450,
           k=1050, b=28, j=52, u=60, photo="item-kesadilya-4-syra.jpg"),
    ]),

    ("Пицца", "Пицца", "Pizza (35 cm)", [
        mk("Пицца 4 сезона", "Төрт мезгил пиццасы", "Four Seasons Pizza", 550,
           k=1700, b=69, j=126, u=112, photo="item-pizza-4-sezona.jpg"),
        mk("Пепперони", "Пепперони", "Pepperoni Pizza", 500,
           k=1500, b=70, j=75, u=110, photo="stock-pepperoni.jpg"),
        mk("Экзотика", "Экзотика", "Exotic Pizza", 750,
           k=1150, b=65, j=45, u=130, photo="item-pizza-ekzotika.jpg"),
        mk("Маргарита", "Маргарита", "Margherita", 400,
           k=1080, b=50, j=45, u=110, photo="stock-margherita.jpg"),
        mk("Терияки", "Терияки", "Teriyaki Pizza", 500,
           k=1900, b=75, j=85, u=210, photo="item-pizza-teriyaki.jpg"),
        mk("Классическая пицца 4 сыра", "Төрт сыр пиццасы", "Classic Four Cheese Pizza", 600,
           k=1350, b=60, j=75, u=100, photo="stock-pizza-4-syra.jpg"),
        mk("Пицца с форелью с соусом Песто", "Песто соусу кошулган форель пиццасы", "Trout Pizza with Pesto Sauce", 700,
           k=1800, b=75, j=60, u=103, photo="item-pizza-forel-pesto.jpg"),
        mk("Куриная со шпинатом", "Тоок эти жана шпинат кошулган пицца", "Chicken & Spinach Pizza", 550,
           k=1250, b=70, j=65, u=110, photo="stock-pizza-kuritsa-shpinat.jpg"),
        mk("Пицца Цезарь", "«Цезарь» пиццасы", "Caesar Pizza", 550,
           k=1850, b=60, j=43, u=120, photo="stock-pizza-cezar.jpg"),
    ]),

    ("Паста", "Паста", "Pasta", [
        mk("Фетучини с форелью", "Форель кошулган фетучини", "Fettuccine with Trout", 600,
           "фетучини, семга, лук, сливки, кабачки, сыр Пармезан",
           "Фетучини, семга, пияз, каймак, кабачки жана пармезан сыры.",
           "Fettuccine, salmon, onion, cream, zucchini, Parmesan cheese.",
           k=850, b=38, j=48, u=70, photo="stock-fetuchini-forel.jpg"),
        mk("Пенне с томатным соусом", "Помидор соусу кошулган пенне", "Penne with Tomato Sauce", 400,
           k=580, b=16, j=18, u=85, photo="item-penne-tomat.jpg"),
        mk("Фетучини Альфредо", "Фетучини «Альфредо»", "Fettuccine Alfredo", 450,
           "фетучини, курица, лук, грибы, сливки, сыр Пармезан",
           "Фетучини, тоок эти, пияз, козу карын, каймак жана пармезан сыры.",
           "Fettuccine, chicken, onion, mushrooms, cream, Parmesan cheese.",
           k=768, b=47, j=42, u=51, photo="stock-fetuchini-alfredo.jpg"),
        mk("Лапша Малайзия", "Малайзия кесмеси", "Malaysia Noodles", 350,
           k=690, b=31, j=20, u=92, photo="item-lapsha-malayziya.jpg"),
        mk("ПП Спагетти с песто", "Песто соусу кошулган ПП спагетти", "Fit Spaghetti with Pesto", 450,
           k=820, b=14, j=48, u=65, photo="stock-spagetti-pesto.jpg"),
        mk("Удон с курицей", "Тоок эти кошулган удон", "Udon with Chicken", 300,
           k=550, b=24, j=16, u=80, photo="item-udon-kuritsa.jpg"),
        mk("Спагетти болоньезе", "Спагетти «Болоньезе»", "Spaghetti Bolognese", 430,
           k=712, b=38, j=32, u=68, photo="stock-bolognese.jpg"),
        mk("Гречневая лапша с овощами", "Жашылчалар кошулган гречка кесмеси", "Buckwheat Noodles with Vegetables", 320,
           k=480, b=320, j=14, u=50, photo="stock-grechka-lapsha.jpg"),
        mk("Спагетти с песто и с курицей", "Песто соусу жана тоок эти кошулган спагетти", "Spaghetti with Pesto & Chicken", 500,
           k=720, b=48, j=31, u=61, photo="item-spagetti-pesto-kuritsa.jpg"),
    ]),

    ("Супы", "Шорполор", "Soups", [
        mk("Рамен с курицей", "Тоок эти кошулган рамен", "Chicken Ramen", 300, k=500, b=30, j=18, u=50, photo="item-ramen.jpg"),
        mk("Рамен с говядиной", "Уй эти кошулган рамен", "Beef Ramen", 330, k=600, b=35, j=24, u=50, photo="item-ramen.jpg"),
        mk("Суп Том ям с креветками", "Креветка кошулган Том Ям шорпосу", "Tom Yum Soup with Shrimp", 650, k=280, b=15, j=10, u=8, photo="item-tom-yam-krevetki.jpg"),
        mk("Куриный суп с лапшой", "Кесме кошулган тоок шорпосу", "Chicken Noodle Soup", 250, k=125, b=7.5, j=5.5, u=5.8, photo="stock-kuriny-sup-lapsha.jpg"),
        mk("ПП Тыквенный крем суп", "ПП ашкабактан даярдалган крем-шорпо", "Fit Pumpkin Cream Soup", 200, k=180, b=8, j=16, u=20, photo="item-pp-tykvenny-krem-sup.jpg"),
        mk("ПП Чечевичный крем суп", "ПП жасмыктан даярдалган крем-шорпо", "Fit Lentil Cream Soup", 250, k=220, b=16, j=8, u=28, photo="stock-chechevichny-sup.jpg"),
        mk("Борщ классический", "Классикалык борщ", "Classic Borscht", 250, k=340, b=10, j=10, u=18, photo="item-borsch-klassichesky.jpg"),
        mk("Суп от Шефа", "Ашпозчунун өзгөчө шорпосу", "Chef's Soup", 250, k=340, b=10, j=10, u=18, photo="item-sup-ot-shefa.jpg"),
        mk("ПП Крем суп с брокколи и цветной капустой", "ПП брокколи жана түстүү капустадан даярдалган крем-шорпо", "Fit Broccoli & Cauliflower Cream Soup", 250, k=280, b=12, j=18, u=22, photo="item-pp-krem-sup-brokkoli.jpg"),
        mk("Солянка мясная", "Эттуу солянка", "Meat Solyanka", 400, k=320, b=22, j=36, u=16, photo="stock-solyanka.jpg"),
        mk("Шорпо с бараниной", "Кой этинен шорпо", "Lamb Shorpo", 300, k=380, b=22, j=22, u=21, photo="stock-shorpo-baranina.jpg"),
        mk("Шорпо с говядиной", "Уй этинен шорпо", "Beef Shorpo", 300, k=480, b=28, j=34, u=22, photo="item-shorpo-govyadina.jpg"),
        mk("Пельмени со сметаной", "Каймак менен пельмендер", "Dumplings with Sour Cream", 250, k=510, b=13, j=34, u=35, photo="stock-pelmeni-smetana.jpg"),
    ]),

    ("Блюда из рыбы и морепродуктов", "Балык жана деңиз азыктарынан жасалган тамактар", "Fish & Seafood", [
        mk("Дорадо на гриле", "Гриль дорадо", "Grilled Dorado", 1400, k=520, b=45, j=34, u=3, photo="stock-dorado-gril.jpg"),
        mk("Филе форели с брокколи", "Брокколи кошулган форель филеси", "Trout Fillet with Broccoli", 650, k=650, b=42, j=38, u=8, photo="item-forel-brokkoli.jpg"),
        mk("ПП Форель со шпинатом", "ПП шпинат кошулган форель", "Fit Trout with Spinach", 800,
           "Пюре из цветной капусты, шпинат, черри, соус песто, лимон, форель на пару",
           "Түстүү капуста пюресси, шпинат, черри помидор, песто соусу, лимон жана бууга бышырылган форель.",
           "Cauliflower purée, spinach, cherry tomatoes, pesto sauce, lemon, steamed trout.",
           k=480, b=40, j=20, u=14, photo="stock-forel-shpinat.jpg"),
        mk("Форель с овощами и рисом", "Жашылчалар жана күрүч менен берилген форель", "Trout with Vegetables & Rice", 550, k=590, b=36, j=22, u=48, photo="stock-forel-ris.jpg"),
    ]),

    ("Гриль", "Гриль", "Grill", [
        mk("Стейк Рибай", "Рибай стейки", "Ribeye Steak", 1400, k=890, b=52, j=70, u=10, photo="item-ribay-steyk.jpg"),
        mk("Стейк Тибон", "Ти-бон стейки", "T-Bone Steak", 1500, k=950, b=58, j=74, u=8, photo="stock-steak-tibon.jpg"),
        mk("Медальоны из телятины с картофелем", "Картошка менен музоо этинен медальондор", "Veal Medallions with Potatoes", 1200, k=720, b=46, j=38, u=28, photo="item-medaliony-teljatina.jpg"),
    ]),

    ("Блюда из говядины и баранины", "Уй жана кой этинен жасалган тамактар", "Beef & Lamb Dishes", [
        mk("Говяжие щечки с картофельным пюре", "Картошка пюреси менен уйдун жаак эти", "Beef Cheeks with Mashed Potatoes", 600, k=610, b=34, j=32, u=36, photo="item-govyazhi-schechki-pyure.jpg"),
        mk("Бефстроганов с пюре", "Пюре менен бефстроганов", "Beef Stroganoff with Mash", 550, k=670, b=30, j=40, u=42, photo="item-befstroganov-pyure.jpg"),
        mk("Куурдак из говядины", "Уй этинен куурдак", "Beef Kuurdak", 600, k=730, b=38, j=48, u=26, photo="stock-kuurdak-govyadina.jpg"),
        mk("Куурдак из баранины", "Кой этинен куурдак", "Lamb Kuurdak", 600, k=790, b=36, j=58, u=22, photo="item-kuurdak-baranina.jpg"),
    ]),

    ("Блюда из курицы", "Тоок этинен жасалган тамактар", "Chicken Dishes", [
        mk("ПП Курица Капрезе", "ПП «Капрезе» тоогу", "Fit Chicken Caprese", 500,
           "помидоры, сыр моцарелла, соус песто, рис на пару",
           "Помидор, моцарелла сыры, песто соусу жана бууга бышырылган күрүч.",
           "Tomatoes, mozzarella, pesto sauce, steamed rice.",
           k=450, b=42, j=18, u=16, photo="stock-kuritsa-kapreze.jpg"),
        mk("Фрикасе с рисом", "Күрүч менен фрикасе", "Chicken Fricassee with Rice", 400, k=430, b=28, j=14, u=42, photo="stock-frikase-ris.jpg"),
        mk("Цитрусовый куриный рулет с овощами", "Жашылчалар менен цитрустуу тоок рулети", "Citrus Chicken Roll with Vegetables", 500, k=510, b=38, j=20, u=24, photo="stock-kuritsa-rulet.jpg"),
        mk("Курица с овощами и рисом", "Жашылчалар жана күрүч менен тоок эти", "Chicken with Vegetables & Rice", 450, k=470, b=30, j=16, u=40, photo="stock-kuritsa-ris.jpg"),
    ]),

    ("Овощи", "Жашылча тамактары", "Vegetable Dishes", [
        mk("Кабачкова корзина с овощным сотэ", "Жашылча сотеси кошулган кабачки себети", "Zucchini Basket with Vegetable Sauté", 250, k=260, b=6, j=12, u=28, photo="stock-kabachkova-korzina.jpg"),
        mk("Картофель с грибами", "Козу карын кошулган картошка", "Potatoes with Mushrooms", 300, k=320, b=7, j=14, u=40, photo="stock-kartofel-gribami.jpg"),
    ]),

    ("Гарниры", "Гарнирлер", "Side Dishes", [
        mk("Картофель фри", "Фри картошкасы", "French Fries", 200, k=360, b=4, j=18, u=48, photo="stock-fri.jpg"),
        mk("Рис на пару", "Бууга бышырылган күрүч", "Steamed Rice", 120, k=180, b=4, j=1, u=38, photo="stock-ris-para.jpg"),
        mk("Овощи на гриле", "Гриль жашылчалары", "Grilled Vegetables", 250, k=140, b=3, j=7, u=16, photo="stock-ovoshi-gril.jpg"),
        mk("Овощи припущенные", "Бууга бышырылган жашылчалар", "Steamed Vegetables", 200, photo="stock-ovoshi-pripushennye.jpg"),
        mk("Цветная капуста в кляре", "Камырга оролуп куурулган түстүү капуста", "Battered Cauliflower", 200, k=192, b=5, j=10, u=20, photo="stock-cvetnaya-kapusta.jpg"),
    ]),

    ("Выпечка", "Нан азыктары", "Bakery", [
        mk("Хлебная корзина ассорти", "Нандардын ассорти себети", "Assorted Bread Basket", 150, k=90, b=3, j=1, u=18, photo="stock-hlebnaya-korzina.jpg"),
        mk("Боорсок со сметаной", "Каймак менен боорсок", "Boorsok with Sour Cream", 250, k=270, b=5, j=14, u=30, photo="item-boorsok-smetana.jpg"),
    ]),

    ("Детское меню", "Балдар менюсу", "Kids Menu", [
        mk("Нагетсы с фри", "Фри менен нагетстер", "Nuggets with Fries", 210, k=210, b=12, j=10, u=18, photo="stock-nagetsy.jpg"),
        mk("Спринг роллы с сыром", "Сыр кошулган спринг-роллдор", "Cheese Spring Rolls", 210, k=210, b=8, j=11, u=20, photo="stock-spring-rolly.jpg"),
        mk("Овощные стики со сметаной", "Каймак менен жашылча таякчалары", "Vegetable Sticks with Sour Cream", 210, k=216, b=5, j=14, u=11, photo="stock-ovoshnye-stiki.jpg"),
        mk("Куриный суп Букварь", "«Букварь» тоок шорпосу", "Bukvar Chicken Soup", 150, k=120, b=10, j=4, u=11, photo="stock-kids-kuriny-sup.jpg"),
        mk("Говяжий суп звездочка", "«Жылдызча» уй шорпосу", "Zvezdochka Beef Soup", 220, k=225, b=14, j=10, u=18, photo="stock-govyazhy-sup-zvezdochka.jpg"),
        mk("Пельмени", "Пельмендер", "Dumplings", 250, k=285, b=12, j=11, u=32, photo="stock-pelmeni-kids.jpg"),
        mk("Фарфале с сыром", "Сыр кошулган фарфалле", "Farfalle with Cheese", 250, k=270, b=11, j=9, u=35, photo="stock-farfalle-syr.jpg"),
        mk("Куриные котлеты с пюре", "Пюре менен тоок котлеттери", "Chicken Cutlets with Mash", 250, k=255, b=18, j=10, u=22, photo="stock-kuritsa-kotlety.jpg"),
        mk("Говяжие фрикадельки с пюре", "Пюре менен уй этинен фрикаделькалар", "Beef Meatballs with Mash", 200, k=180, b=14, j=7, u=15, photo="stock-govyazhi-frikadelki.jpg"),
        mk("Осьминожки (сосиски, фри)", "«Осьминожки» (сосискалар жана фри картошкасы)", "Octopus Sausages with Fries", 200, k=186, b=7, j=9, u=18, photo="stock-osminozhki.jpg"),
        mk("Ужин от папы", "Атамдын кечки тамагы", "Daddy's Dinner", 350, k=540, b=18, j=29, u=47, photo="item-uzhin-ot-papy.jpg"),
        mk("Шоколадные блины", "Шоколад кошулган блинчиктер", "Chocolate Pancakes", 150, k=126, b=4, j=5, u=17, photo="stock-shokoladnye-bliny.jpg"),
        mk("Банан с шоколадом", "Шоколад кошулган банан", "Banana with Chocolate", 150, k=165, b=2, j=7, u=24, photo="stock-banan-shokolad.jpg"),
        mk("Фрукты по сезону в стаканчике", "Мезгилдик мөмө-жемиштер стаканда", "Seasonal Fruit Cup", 100, k=96, b=1, j=0, u=22, photo="stock-frukty-sezon.jpg"),
        mk("Венские вафли с шоколадным соусом", "Шоколад соусу менен веналык вафлилер", "Vienna Waffles with Chocolate Sauce", 250, k=610, b=11, j=29, u=75, photo="item-venskie-vafli.jpg"),
    ]),

    ("Кофе", "Кофелер", "Coffee", [
        mk("Эспрессо", "Эспрессо", "Espresso", 180,
           "Крепкий бодрящий глоток классического эспрессо с плотной бархатистой пенкой крема. 30/60 мл",
           "Классикалык эспрессонун катуу, сергитүүчү жуткуму, тыгыз бархат көбүгү менен. 30/60 мл",
           "A strong, invigorating sip of classic espresso with a dense velvety crema. 30/60 ml.",
           photo="espresso.jpg"),
        mk("Американо", "Американо", "Americano", 200,
           "Классический мягкий эспрессо с добавлением горячей воды для чистого кофейного вкуса. 180 мл",
           "Таза кофе даамы үчүн ысык суу кошулган жумшак классикалык эспрессо. 180 мл",
           "Classic smooth espresso with hot water added for a clean coffee taste. 180 ml.",
           photo="americano.jpg"),
        mk("Айс Американо", "Айс Американо", "Iced Americano", 200,
           "Освежающий холодный американо со льдом — идеальный бодрящий заряд в жаркий день. 180 мл",
           "Ысык күндөрдө сергитүүчү муздак американо. 180 мл",
           "Refreshing cold Americano with ice — a perfect boost on a hot day. 180 ml.",
           photo="ice-americano.jpg"),
        mk("Бамбл", "Бамбл", "Bumble", 270,
           "Яркий слоистый микс бодрящего эспрессо, свежевыжатого апельсинового сока и карамельного сиропа. 400 мл",
           "Эспрессо, жаңы сыгылган апельсин ширеси жана карамель сиропунун жаркыраган катмардуу микси. 400 мл",
           "A vivid layered mix of espresso, fresh orange juice and caramel syrup. 400 ml.",
           photo="bumble.jpg"),
        mk("Капучино", "Капучино", "Cappuccino", 250,
           "Идеальный баланс насыщенного эспрессо и пышной, нежной молочной пенки. 200/300 мл",
           "Каныккан эспрессо жана жумшак сүт көбүгүнүн идеалдуу тең салмактуулугу. 200/300 мл",
           "Perfect balance of rich espresso and airy, delicate milk foam. 200/300 ml.",
           photo="cappuccino.jpg"),
        mk("Айс Капучино", "Айс Капучино", "Iced Cappuccino", 300,
           "Освежающий эспрессо с холодным молоком и пышной устойчивой пенкой со льдом. 400 мл",
           "Муздак сүт жана туруктуу көбүк менен сергитүүчү эспрессо. 400 мл",
           "Refreshing espresso with cold milk and stable foam over ice. 400 ml.",
           photo="ice-cappuccino.jpg"),
        mk("Латте", "Латте", "Latte", 270,
           "Нежный молочно-кофейный напиток с мягким вкусом и шелковистой текстурой. 300/400 мл",
           "Жумшак даамы жана жибек текстурасы бар назик сүт-кофе ичимдиги. 300/400 мл",
           "A gentle milk-coffee drink with a soft taste and silky texture. 300/400 ml.",
           photo="latte.jpg"),
        mk("Айс-латте", "Айс-латте", "Iced Latte", 250,
           "Прохладный молочный эспрессо-микс со льдом для легкого и освежающего кофе-паузы. 400 мл",
           "Жеңил жана сергитүүчү кофе-тыныгуу үчүн муздак сүт-эспрессо микси. 400 мл",
           "A cool milk-espresso mix over ice for a light, refreshing coffee break. 400 ml.",
           photo="ice-latte.jpg"),
        mk("Флэт Уайт", "Флэт Уайт", "Flat White", 270,
           "Двойной эспрессо с тонким слоем бархатистого взбитого молока для любителей яркого кофе. 250 мл",
           "Ачык даамдуу кофени жактыргандар үчүн эки эспрессо жана жука бархат сүт катмары. 250 мл",
           "Double espresso with a thin layer of velvety steamed milk for bold coffee lovers. 250 ml.",
           photo="flat-white.jpg"),
        mk("Раф", "Раф", "Raf Coffee", 270,
           "Ванильно-сливочный десертный кофе с невероятно нежной, тающей текстурой. 300 мл",
           "Ванилдүү-каймактуу десерттик кофе, өтө назик, эрип турган текстурасы менен. 300 мл",
           "Vanilla-cream dessert coffee with an incredibly delicate, melting texture. 300 ml.",
           photo="raf.jpg"),
        mk("Моккачино", "Моккачино", "Mochaccino", 260,
           "Гармоничное сочетание эспрессо, горячего молока и ароматного шоколада. 300 мл",
           "Эспрессо, ысык сүт жана жыпар жыттуу шоколаддын үйлөшкөн айкалышы. 300 мл",
           "A harmonious blend of espresso, hot milk and aromatic chocolate. 300 ml.",
           photo="mocaccino.jpg"),
        mk("Какао", "Какао", "Cocoa", 250,
           "Уютный согревающий напиток из натурального шоколадного какао на нежном молоке. 300 мл",
           "Табигый шоколад какаосунан назик сүттө даярдалган жылытуучу ичимдик. 300 мл",
           "A cozy warming drink made from natural chocolate cocoa with gentle milk. 300 ml.",
           photo="cocoa.jpg"),
        mk("Какао с маршмеллоу", "Какао с маршмеллоу", "Cocoa with Marshmallows", 260,
           "Ароматный какао с ванильными мини-маршмеллоу, тающими в горячей пенке. 300 мл",
           "Ысык көбүктө эрип турган ванилдүү мини-маршмеллоу менен жыпар жыттуу какао. 300 мл",
           "Aromatic cocoa with vanilla mini marshmallows melting into the hot foam. 300 ml.",
           photo="cocoa-marshmallow.jpg"),
        mk("Горячий шоколад", "Горячий шоколад", "Hot Chocolate", 260,
           "Густой, насыщенный десерт из настоящего растопленного шоколада со сливочным вкусом. 200 мл",
           "Чыныгы эриген шоколаддан жасалган коюу, каймактуу даамдагы десерт. 200 мл",
           "A thick, rich dessert made from real melted chocolate with a creamy taste. 200 ml.",
           photo="hot-chocolate.jpg"),
        mk("Матча зелёная", "Матча зелёная", "Green Matcha", 270,
           "Японский зеленый чай матча на нежном молоке — суперфуд для бодрости и гармонии. 200 мл",
           "Назик сүттөгү жапон матча жашыл чайы — сергектик жана гармония үчүн суперфуд. 200 мл",
           "Japanese green matcha tea with gentle milk — a superfood for energy and balance. 200 ml.",
           photo="matcha-green.jpg"),
        mk("Матча синяя", "Матча синяя", "Blue Matcha", 270,
           "Экзотический напиток из цветов анчана с мягким сливочным вкусом и синим оттенком. 200 мл",
           "Анчан гүлдөрүнөн жасалган, жумшак каймак даамдуу жана көк түстөгү экзотикалык ичимдик. 200 мл",
           "An exotic drink made from butterfly pea flowers with a soft creamy taste and blue hue. 200 ml.",
           photo="matcha-blue.jpg"),
        mk("Матча розовая", "Матча розовая", "Pink Matcha", 270,
           "Нежный напиток на основе сублимированной питахайи с легким фруктовым ароматом. 200 мл",
           "Сублимацияланган питахая негизиндеги, жеңил мөмө жыттуу назик ичимдик. 200 мл",
           "A delicate drink based on freeze-dried pitahaya with a light fruity aroma. 200 ml.",
           photo="matcha-pink.jpg"),
    ]),

    ("Bubble Tea", "Bubble tea (баббл ти)", "Bubble Tea", [
        mk("Bubble tea киви-груша", "Bubble tea киви-груша", "Bubble Tea Kiwi-Pear", 270,
           "Освежающий чайный напиток с шариками тапиоки, сочным сиропом киви и ароматной груши Дюшес. 420 мл",
           "Тапиока шарчалары, ширелүү киви сиропу жана Дюшес алмурутунун жыты кошулган сергитүүчү чай ичимдиги. 420 мл",
           "A refreshing tea drink with tapioca pearls, juicy kiwi syrup and Duchess pear aroma. 420 ml.",
           photo="bt-kiwi-pear.jpg"),
        mk("Bubble tea манго-кокос", "Bubble tea манго-кокос", "Bubble Tea Mango-Coconut", 270,
           "Экзотический чайный коктейль с шариками тапиоки, тропическим манго и сливочным кокосовым оттенком. 380 мл",
           "Тапиока шарчалары, тропикалык манго жана каймактуу кокос менен экзотикалык чай коктейли. 380 мл",
           "An exotic tea cocktail with tapioca pearls, tropical mango and creamy coconut notes. 380 ml.",
           photo="bt-mango-coconut.jpg"),
        mk("Bubble tea манго-маракуйя", "Bubble tea манго-маракуйя", "Bubble Tea Mango-Passionfruit", 270,
           "Яркий фруктовый чай с тапиокой, натуральным пюре и сиропом манго и кислинкой маракуйи. 410 мл",
           "Тапиока, табигый манго пюресси жана маракуйянын кычкылтыгы кошулган жаркыраган мөмө чайы. 410 мл",
           "A vivid fruity tea with tapioca, natural mango purée and syrup, and tangy passionfruit. 410 ml.",
           photo="bt-mango-maracuya.jpg"),
        mk("Bubble tea ягодный", "Bubble tea ягодный", "Bubble Tea Berry", 270,
           "Ягодный чайный микс с шариками тапиоки, спелой вишней и ароматной свежемороженой малиной. 420 мл",
           "Тапиока шарчалары, бышкан алча жана муздатылган таза малина кошулган мөмө чай микси. 420 мл",
           "A berry tea mix with tapioca pearls, ripe cherry and aromatic frozen raspberry. 420 ml.",
           photo="bt-berry2.jpg"),
    ]),

    ("Лимонады", "Лимонадтар", "Lemonades", [
        mk("Ананасовый лимонад", "Ананасовый лимонад", "Pineapple Lemonade", 220,
           "Сочный тропический лимонад со спелым ананасом и искрящимися пузырьками. 400 мл / 1 л",
           "Бышкан ананас жана жаркыраган көбүкчөлөр менен ширелүү тропикалык лимонад. 400 мл / 1 л",
           "A juicy tropical lemonade with ripe pineapple and sparkling bubbles. 400 ml / 1 L.",
           photo="lemonade-pineapple.jpg"),
        mk("Тропический лимонад", "Тропический лимонад", "Tropical Lemonade", 220,
           "Яркий микс экзотических фруктов, подаряющий ощущение летнего отдыха. 400 мл / 1 л",
           "Жайкы эс алуунун сезимин тартуулаган экзотикалык мөмөлөрдүн жаркыраган микси. 400 мл / 1 л",
           "A vivid mix of exotic fruits that brings the feeling of summer vacation. 400 ml / 1 L.",
           photo="lemonade-tropical.jpg"),
        mk("Ягодный лимонад", "Ягодный лимонад", "Berry Lemonade", 220,
           "Насыщенный освежающий коктейль из спелых лесных и садовых ягод. 400 мл / 1 л",
           "Бышкан токой жана бак-дарак жемиштеринен даярдалган каныккан сергитүүчү коктейль. 400 мл / 1 л",
           "A rich, refreshing cocktail of ripe wild and garden berries. 400 ml / 1 L.",
           photo="lemonade-berry.jpg"),
        mk("Манго-маракуйя", "Манго-маракуйя", "Mango-Passionfruit", 220,
           "Сладковато-пряный лимонад с ярким дуэтом спелого манго и кислинкой маракуйи. 400 мл / 1 л",
           "Бышкан манго жана маракуйянын кычкылтыгынын дуэти менен таттуу-жыпар лимонад. 400 мл / 1 л",
           "A sweet-spicy lemonade with a vivid duet of ripe mango and tangy passionfruit. 400 ml / 1 L.",
           photo="lemonade-mango-maracuya.jpg"),
        mk("Манго-клубника", "Манго-клубника", "Mango-Strawberry", 220,
           "Сочное сочетание сочной клубники и тропического сочного манго. 400 мл / 1 л",
           "Ширелүү кулпунай жана тропикалык манго айкалышы. 400 мл / 1 л",
           "A juicy combination of ripe strawberry and tropical mango. 400 ml / 1 L.",
           photo="lemonade-mango-strawberry.jpg"),
        mk("Маракуйя-Ананас", "Маракуйя-Ананас", "Passionfruit-Pineapple", 220,
           "Взрывной тропический коктейль с бодрящей кислинкой и фруктовым ароматом. 400 мл / 1 л",
           "Сергитүүчү кычкылтыгы жана мөмө жыты бар жарылма тропикалык коктейль. 400 мл / 1 л",
           "An explosive tropical cocktail with an invigorating tang and fruity aroma. 400 ml / 1 L.",
           photo="lemonade-maracuya-pineapple.jpg"),
        mk("Мохито", "Мохито", "Mojito", 220,
           "Освежающая классика с душистой мятой, сочным лаймом и охлаждающим льдом. 400 мл / 1 л",
           "Жыпар жыттуу мята, ширелүү лайм жана муз менен сергитүүчү классика. 400 мл / 1 л",
           "A refreshing classic with fragrant mint, juicy lime and cooling ice. 400 ml / 1 L.",
           photo="mojito.jpg"),
        mk("Клубничное мохито", "Клубничное мохито", "Strawberry Mojito", 220,
           "Ягодная вариация мохито с добавлением ароматной свежей клубники. 400 мл / 1 л",
           "Жыпар жыттуу таза кулпунай кошулган мохитонун мөмө версиясы. 400 мл / 1 л",
           "A berry take on mojito with fragrant fresh strawberries. 400 ml / 1 L.",
           photo="mojito-strawberry.jpg"),
        mk("Малиновый мохито", "Малиновый мохито", "Raspberry Mojito", 220,
           "Яркий мятно-лаймовый микс со спелой ароматной малиной. 400 мл / 1 л",
           "Бышкан жыпар жыттуу малина кошулган жаркыраган мята-лайм микси. 400 мл / 1 л",
           "A vivid mint-lime mix with ripe fragrant raspberries. 400 ml / 1 L.",
           photo="mojito-raspberry.jpg"),
        mk("Цитрусовый мохито", "Цитрусовый мохито", "Citrus Mojito", 220,
           "Бодрящий заряд сочных цитрусов с мятой и искрящейся содовой. 400 мл / 1 л",
           "Мята жана көбүкчөлүү сода менен ширелүү цитрустардын сергитүүчү заряды. 400 мл / 1 л",
           "An invigorating boost of juicy citrus with mint and sparkling soda. 400 ml / 1 L.",
           photo="mojito-citrus.jpg"),
    ]),

    ("Фирменные байские чаи", "Фирмалык байча чайлар", "Signature Bai Teas", [
        mk("Байский клубничный", "Байский клубничный", "Bai Strawberry", 300,
           "Ароматный черный чай с натуральной клубникой и ложкой натурального меда. 600 мл",
           "Табигый кулпунай жана бир кашык табигый бал кошулган жыпар жыттуу кара чай. 600 мл",
           "Aromatic black tea with natural strawberries and a spoon of natural honey. 600 ml.",
           photo="tea-strawberry.jpg"),
        mk("Байский апельсиновый", "Байский апельсиновый", "Bai Orange", 300,
           "Насыщенный черный чай с сочными дольками апельсина и натуральным медом. 600 мл",
           "Ширелүү апельсин бөлүкчөлөрү жана табигый бал кошулган каныккан кара чай. 600 мл",
           "Rich black tea with juicy orange slices and natural honey. 600 ml.",
           photo="tea-orange.jpg"),
        mk("Чай с облепихой и имбирем", "Чай с облепихой и имбирем", "Sea Buckthorn & Ginger Tea", 300,
           "Согревающий витаминный микс с облепихой, имбирем, лаймом, корицей и анисом. 600 мл",
           "Чычырканак, имбирь, лайм, корица жана анис менен жылытуучу витамин микси. 600 мл",
           "A warming vitamin mix with sea buckthorn, ginger, lime, cinnamon and anise. 600 ml.",
           photo="tea-seabuckthorn-ginger.jpg"),
        mk("Малина-Манго", "Малина-Манго", "Raspberry-Mango", 300,
           "Ароматный чай со спелой малиной, манго, тимьяном, мятой и пряным анисом. 600 мл",
           "Бышкан малина, манго, кекик, мята жана анис кошулган жыпар жыттуу чай. 600 мл",
           "Aromatic tea with ripe raspberries, mango, thyme, mint and spicy anise. 600 ml.",
           photo="tea-raspberry-mango.jpg"),
        mk("Бора-Бора", "Бора-Бора", "Bora-Bora", 300,
           "Тропический чарующий чай с грейпфрутом, манго, маракуйей, мятой и корицей. 600 мл",
           "Грейпфрут, манго, маракуйя, мята жана корица менен тропикалык суктандыруучу чай. 600 мл",
           "An enchanting tropical tea with grapefruit, mango, passionfruit, mint and cinnamon. 600 ml.",
           photo="tea-borabora.jpg"),
        mk("Ханский чай", "Ханский чай", "Khan Tea", 300,
           "Благородный купаж черного и зеленого чая с сочным лимоном и медовой сладостью. 600 мл",
           "Ширелүү лимон жана бал таттуулугу менен кара жана жашыл чайдын асыл аралашмасы. 600 мл",
           "A noble blend of black and green tea with juicy lemon and honey sweetness. 600 ml.",
           photo="tea-khan.jpg"),
        mk("Байский ягодный чай", "Байский ягодный чай", "Bai Berry Tea", 300,
           "Витаминный сбор из зеленого и черного чая с малиной, черникой, смородиной и медом. 600 мл",
           "Малина, көк карагат, кара карагат жана бал кошулган жашыл жана кара чайдын витамин жыйнагы. 600 мл",
           "A vitamin blend of green and black tea with raspberry, blueberry, currant and honey. 600 ml.",
           photo="tea-bai-berry.jpg"),
        mk("Фруктовый чай", "Фруктовый чай", "Fruit Tea", 300,
           "Богатый черный чай с мятой, натуральным медом и ассорти сушеных фруктов. 600 мл",
           "Мята, табигый бал жана кургатылган мөмөлөрдүн ассортиси менен бай кара чай. 600 мл",
           "Rich black tea with mint, natural honey and an assortment of dried fruits. 600 ml.",
           photo="tea-fruit.jpg"),
    ]),

    ("Элитные сорта чая", "Элита чайлары", "Premium Teas", [
        mk("Китайский жасмин", "Кытай жасмини", "Chinese Jasmine", 250,
           "Изысканный зеленый чай с утонченным натуральным ароматом цветов жасмина. 600 мл",
           "Жасмин гүлдөрүнүн назик табигый жыты бар сонун жашыл чай. 600 мл",
           "An exquisite green tea with a delicate natural jasmine flower aroma. 600 ml.",
           photo="tea-chrysanthemum.jpg"),
        mk("Сливочный Улун", "Сливочный Улун", "Creamy Oolong", 250,
           "Знаменитый улун с мягким, тающим сливочно-карамельным послевкусием. 600 мл",
           "Жумшак, эрип турган каймак-карамель артдаамы бар атактуу улун чай. 600 мл",
           "A famous oolong with a soft, melting creamy-caramel aftertaste. 600 ml.",
           photo="tea-oolong.jpg"),
        mk("Ассам", "Ассам", "Assam", 250,
           "Классический индийский черный чай с терпким, солодовым вкусом и глубоким цветом. 600 мл",
           "Курч, солод даамы жана терең түсү бар классикалык индия кара чайы. 600 мл",
           "A classic Indian black tea with a brisk, malty taste and deep color. 600 ml.",
           photo="tea-assam.jpg"),
        mk("Эрл Грей", "Эрл Грей", "Earl Grey", 250,
           "Благородный черный чай с добавлением манящего масла бергамота. 600 мл",
           "Тартымдуу бергамот майы кошулган асыл кара чай. 600 мл",
           "A noble black tea with alluring bergamot oil. 600 ml.",
           photo="tea-earlgrey.jpg"),
        mk("Фруктовый пунш", "Фруктовый пунш", "Fruit Punch", 250,
           "Яркий ягодно-фруктовый чайный напиток с насыщенным вкусом и ароматом. 600 мл",
           "Каныккан даамы жана жыты бар жаркыраган мөмө-жемиш чай ичимдиги. 600 мл",
           "A vivid berry-fruit tea drink with a rich taste and aroma. 600 ml.",
           photo="tea-punch.jpg"),
        mk("Пуэр", "Пуэр", "Pu-erh", 250,
           "Выдержанный китайский чай с глубоким древесно-землистым вкусом и тонизирующим эффектом. 600 мл",
           "Терең жыгач-топурак даамы жана тондоочу таасири бар эскирген кытай чайы. 600 мл",
           "An aged Chinese tea with a deep, earthy-woody taste and a tonic effect. 600 ml.",
           photo="tea-puerh.jpg"),
        mk("Китайский зеленый чай с хризантемой", "Хризантема кошулган кытай жашыл чайы", "Chinese Green Tea with Chrysanthemum", 250,
           "Целебный зеленый чай с легкими цветочными нотами хризантемы. 600 мл",
           "Хризантеманын жеңил гүл нотасы бар айыктыруучу жашыл чай. 600 мл",
           "A healing green tea with light floral chrysanthemum notes. 600 ml.",
           photo="tea-jasmine.jpg"),
        mk("Чай черный", "Чай кара", "Black Tea", 170,
           "Классический черный чай с крепким, насыщенным и бодрящим вкусом. 600 мл",
           "Катуу, каныккан жана сергитүүчү даамы бар классикалык кара чай. 600 мл",
           "Classic black tea with a strong, rich and invigorating taste. 600 ml.",
           photo="tea-black.jpg"),
        mk("Зеленый чай", "Жашыл чай", "Green Tea", 170,
           "Традиционный зеленый чай с чистым, свежим и травянистым оттенком. 600 мл",
           "Таза, жаңы жана чөптүү даамы бар салттуу жашыл чай. 600 мл",
           "Traditional green tea with a clean, fresh, grassy note. 600 ml.",
           photo="tea-green.jpg"),
    ]),

    ("Молочные коктейли", "Милкшейктер", "Milkshakes", [
        mk("Банан шейк", "Банан шейк", "Banana Shake", 270, photo="cat-milkshake.jpg"),
        mk("Клубничный шейк", "Клубничный шейк", "Strawberry Shake", 270, photo="cat-milkshake.jpg"),
        mk("Шоколадный шейк", "Шоколадный шейк", "Chocolate Shake", 270, photo="cat-milkshake.jpg"),
        mk("Банан-шоколад шейк", "Банан-шоколад шейк", "Banana-Chocolate Shake", 270, photo="cat-milkshake.jpg"),
        mk("Малиновый шейк", "Малиновый шейк", "Raspberry Shake", 270, photo="cat-milkshake.jpg"),
    ]),

    ("Смузи", "Смузилер", "Smoothies", [
        mk("Банан-киви", "Банан-киви", "Banana-Kiwi", 280, photo="cat-smuzi.jpg"),
        mk("Банан-клубника", "Банан-клубника", "Banana-Strawberry", 280, photo="cat-smuzi.jpg"),
        mk("Банан-малина", "Банан-малина", "Banana-Raspberry", 280, photo="cat-smuzi.jpg"),
        mk("Киви-клубника", "Киви-клубника", "Kiwi-Strawberry", 280, photo="cat-smuzi.jpg"),
        mk("Ягодный смузи", "Ягодный смузи", "Berry Smoothie", 280, photo="cat-smuzi.jpg"),
    ]),

    ("Фитнес коктейли", "Фитнес коктейлдер", "Fitness Shakes", [
        mk("Зелёный детокс-коктейль", "Жашыл детокс-коктейль", "Green Detox Shake", 400,
           "Очищающий микс: шпинат, яблоко, огурец, киви и лимон. Максимум пользы!",
           "Тазалоочу микс: шпинат, алма, бадыраң, киви жана лимон. Максималдуу пайда!",
           "A cleansing mix: spinach, apple, cucumber, kiwi and lemon. Maximum benefit!",
           photo="fit-detox.jpg"),
        mk("Белковый коктейль с бананом", "Банан кошулган белок коктейли", "Protein Shake with Banana", 500,
           "Протеиновый заряд: растительное молоко, белок, банан и семена льна.",
           "Протеин заряды: өсүмдүк сүтү, белок, банан жана зыгыр үрөндөрү.",
           "A protein boost: plant milk, protein, banana and flax seeds.",
           photo="fit-protein-banana.jpg"),
        mk("Овсяный смузи с ягодами", "Мөмө-жемиштер кошулган сулу смузиси", "Oat Smoothie with Berries", 400,
           "Питательный смузи: овес, малина, клубника, кефир и натуральный мед.",
           "Аш болумдуу смузи: сулу, малина, кулпунай, кефир жана табигый бал.",
           "A nourishing smoothie: oats, raspberry, strawberry, kefir and natural honey.",
           photo="fit-oat-berry.jpg"),
        mk("Коктейль с авокадо и шпинатом", "Авокадо жана шпинат кошулган коктейль", "Avocado & Spinach Shake", 400,
           "Суперфуд-коктейль: авокадо, шпинат, огурец, кефир, лимон и семена чиа.",
           "Суперфуд коктейль: авокадо, шпинат, бадыраң, кефир, лимон жана чиа үрөндөрү.",
           "A superfood shake: avocado, spinach, cucumber, kefir, lemon and chia seeds.",
           photo="fit-avocado-spinach.jpg"),
        mk("Шоколадно-банановый ПП-коктейль", "Шоколад-банан ПП-коктейли", "Chocolate-Banana Fit Shake", 400,
           "Полезный десерт: банан, какао, миндальное молоко и семена льна.",
           "Пайдалуу десерт: банан, какао, бадам сүтү жана зыгыр үрөндөрү.",
           "A healthy dessert: banana, cocoa, almond milk and flax seeds.",
           photo="fit-choco-banana.jpg"),
    ]),

    ("Свежевыжатые соки", "Фреш ширелер", "Fresh Juices", [
        mk("Гранат", "Гранат", "Pomegranate", 300, photo="juice-pomegranate.jpg"),
        mk("Апельсин", "Апельсин", "Orange", 300, photo="juice-orange.jpg"),
        mk("Яблоко", "Яблоко", "Apple", 260, photo="juice-apple.jpg"),
        mk("Морковь", "Морковь", "Carrot", 260, photo="juice-carrot.jpg"),
        mk("Красная свекла", "Красная свекла", "Red Beetroot", 260, photo="juice-beetroot.jpg"),
    ]),

    ("Напитки", "Суусундуктар", "Beverages", [
        mk("Coca-Cola / Fanta / Sprite", "Coca-Cola / Fanta / Sprite", "Coca-Cola / Fanta / Sprite", 140,
           "500 мл / 1 л", "500 мл / 1 л", "500 ml / 1 L", photo="cola-cans.jpg"),
        mk("Coca-Cola / Fanta / Sprite (стекло/банка)", "Coca-Cola / Fanta / Sprite (айнек/банка)", "Coca-Cola / Fanta / Sprite (glass/can)", 110,
           "250 мл / 450 мл", "250 мл / 450 мл", "250 ml / 450 ml", photo="cola-glass.jpg"),
        mk("Ширелер / Сок", "Ширелер / Сок", "Juice", 260, "1 л", "1 л", "1 L", photo="juice-shirel.jpg"),
        mk("Ширелер / Сок стекло", "Ширелер / Сок стекло", "Juice (glass)", 150, "200 мл", "200 мл", "200 ml", photo="juice-shirel-glass.jpg"),
        mk("Вода Asu (б/газа, с/газом)", "Asu суусу (газсыз, газдуу)", "Asu Water (still/sparkling)", 50,
           "500 мл / 1 л", "500 мл / 1 л", "500 ml / 1 L", photo="water-asu2.jpg"),
        mk("Джалал-Абад №27", "Жалал-Абад №27", "Jalal-Abad No. 27", 110,
           "500 мл / 1 л", "500 мл / 1 л", "500 ml / 1 L", photo="water-jalalabad2.jpg"),
        mk("Боржоми", "Боржоми", "Borjomi", 150, "330 мл / 500 мл", "330 мл / 500 мл", "330 ml / 500 ml", photo="water-borjomi2.jpg"),
        mk("Легенда (б/газа, с/газом)", "Легенда (газсыз, газдуу)", "Legenda (still/sparkling)", 50,
           "500 мл / 1 л", "500 мл / 1 л", "500 ml / 1 L", photo="water-legenda3.jpg"),
    ]),

    ("Добавки и упаковка", "Кошумчалар", "Add-ons & Packaging", [
        mk("Имбирь", "Имбирь", "Ginger", 80, "50 г", "50 г", "50 g", photo="add-ginger.jpg"),
        mk("Мята", "Мята", "Mint", 50, "5 г", "5 г", "5 g", photo="add-mint.jpg"),
        mk("Мёд", "Бал", "Honey", 100, "50 г", "50 г", "50 g", photo="add-honey.jpg"),
        mk("Лимон", "Лимон", "Lemon", 80, "50 г", "50 г", "50 g", photo="add-lemon.jpg"),
        mk("Лайм", "Лайм", "Lime", 100, "50 г", "50 г", "50 g", photo="add-lime.jpg"),
        mk("Апельсин", "Апельсин", "Orange", 80, "50 г", "50 г", "50 g", photo="add-orange.jpg"),
        mk("Банан", "Банан", "Banana", 100, "100 г", "100 г", "100 g", photo="add-banana.jpg"),
        mk("Топинг (шоколад / клубника)", "Топинг (шоколад / кулпунай)", "Topping (chocolate / strawberry)", 50, "20 г", "20 г", "20 g", photo="add-topping.jpg"),
        mk("Сироп в ассортименте", "Сироп ассортименти", "Assorted Syrup", 50, "20 г", "20 г", "20 g", photo="add-syrup.jpg"),
        mk("Молоко", "Сүт", "Milk", 50, "50/100 г", "50/100 г", "50/100 g", photo="add-milk.jpg"),
        mk("Сливки", "Каймак", "Cream", 100, "50 г", "50 г", "50 g", photo="add-cream.jpg"),
        mk("Контейнер / стаканы", "Идиш / стакандар", "Container / Cups", 20, "1 шт", "1 шт", "1 pc", photo="add-cups.jpg"),
    ]),

    ("Спортивное питание", "Спорттук азыктар", "Sports Nutrition", [
        mk("Rule 1 Whey Protein (Соленая карамель)", "Rule 1 Whey Protein (Туздалган карамель)", "Rule 1 Whey Protein (Salted Caramel)", 200,
           "Протеин. 33 г (1 скуп)", "Протеин. 33 г (1 скуп)", "Protein. 33 g (1 scoop)", photo="supp-whey.jpg"),
        mk("Dennis James Lean Muscle Mass Gainer", "Dennis James Lean Muscle Mass Gainer", "Dennis James Lean Muscle Mass Gainer", 250,
           "Гейнер. 100 г (1 скуп)", "Гейнер. 100 г (1 скуп)", "Gainer. 100 g (1 scoop)", photo="supp-gainer.jpg"),
        mk("Flex Wheeler BURN Fat Burner Powder", "Flex Wheeler BURN Fat Burner Powder", "Flex Wheeler BURN Fat Burner Powder", 180,
           "Бёрн. 1 порция (5 г)", "Бёрн. 1 порция (5 г)", "Fat burner. 1 serving (5 g)", photo="supp-burn.jpg"),
        mk("Optimum Nutrition Essential Amin.O. Energy", "Optimum Nutrition Essential Amin.O. Energy", "Optimum Nutrition Essential Amin.O. Energy", 170,
           "Аминокислоты. 9 г (2 скупа)", "Аминокислоты. 9 г (2 скупа)", "Amino acids. 9 g (2 scoops)", photo="supp-amino.jpg"),
        mk("Flex Wheeler BOOM Pre-Workout", "Flex Wheeler BOOM Pre-Workout", "Flex Wheeler BOOM Pre-Workout", 180,
           "Бум. 1 порция (8.5 г)", "Бум. 1 порция (8.5 г)", "Pre-workout. 1 serving (8.5 g)", photo="supp-preworkout.jpg"),
        mk("Rule 1 BCAA 3:1:2 (Голубая малина)", "Rule 1 BCAA 3:1:2 (Көк малина)", "Rule 1 BCAA 3:1:2 (Blue Raspberry)", 150,
           "БСАА. 1 порция (7.2 г)", "БСАА. 1 порция (7.2 г)", "BCAA. 1 serving (7.2 g)", photo="supp-bcaa.jpg"),
        mk("Olimp ISO PLUS + L-Carnitine", "Olimp ISO PLUS + L-Carnitine", "Olimp ISO PLUS + L-Carnitine", 130,
           "Изотоник. 17.5 г (1 скуп)", "Изотоник. 17.5 г (1 скуп)", "Isotonic. 17.5 g (1 scoop)", photo="supp-isoplus.jpg"),
    ]),
]


class Command(BaseCommand):
    help = "Создаёт ресторан «Булак Sport Community» + филиал + полное меню (RU/KY/EN) с фото"

    def add_arguments(self, parser):
        parser.add_argument("--name", default="Булак Sport Community", help="Название заведения (RU)")
        parser.add_argument("--slug", default="bulak-2", help="Slug ресторана (bulak уже занят другим рестораном)")
        parser.add_argument("--name-ky", default="Булак Sport Community", help="Название (KY)")
        parser.add_argument("--name-en", default="Bulak Sport Community", help="Название (EN)")
        parser.add_argument("--address", default="", help="Адрес филиала")
        parser.add_argument("--phone", default="+996 555 88 66 36", help="Телефон филиала")
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
        if slug == "bulak":
            raise CommandError("slug='bulak' уже занят другим рестораном — используй --slug с другим значением (по умолчанию bulak-2).")
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
                for name_r, name_k, name_e, price, desc_r, desc_k, desc_e, photo_key, k, b, j, u in items:
                    kbju = f" КБЖУ={k}/{b}/{j}/{u}" if any(v is not None for v in (k, b, j, u)) else ""
                    self.log(f"   • {name_r} — {price} сом  ({name_e} / {name_k})  [{photo_key}]{kbju}")
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

            for item_idx, (name_r, name_k, name_e, price, desc_r, desc_k, desc_e, photo_key, k, b, j, u) in enumerate(items):
                item = Item(
                    restaurant=restaurant,
                    name_ru=name_r, name_ky=name_k, name_en=name_e,
                    description_ru=desc_r, description_ky=desc_k, description_en=desc_e,
                    base_price=price,
                    calories=k, protein=b, fat=j, carbs=u,
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
        self.log("📷 Фото категорий — кадры, вырезанные напрямую из фотографий блюд в PDF-меню заведения.")
        self.log("")
        self.log("📌 Если нужно привязать аккаунт владельца к ресторану:")
        self.log("   python manage.py shell")
        self.log("   from core.models import Restaurant, Membership")
        self.log("   from django.contrib.auth.models import User")
        self.log("   u = User.objects.get(username='ЛОГИН_ВЛАДЕЛЬЦА')")
        self.log(f"   r = Restaurant.objects.get(slug='{slug}')")
        self.log("   Membership.objects.get_or_create(user=u, restaurant=r)")
