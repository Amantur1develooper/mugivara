"""
Django management command to import Jannat Resort Osh restaurant menu.

Usage:
    python manage.py import_jannat
    python manage.py import_jannat --dry-run       # parse only, no DB writes
    python manage.py import_jannat --no-images     # skip image downloads
    python manage.py import_jannat --reset         # delete existing and reimport
    python manage.py import_jannat --pexels-key YOUR_KEY
"""

import os
from decimal import Decimal

from django.core.management.base import BaseCommand

# ─── Full menu data extracted from аля кард 2026.pdf ─────────────────────────

RESTAURANT = {
    "name_ru": "Жаннат Резорт Ош",
    "name_ky": "Жаннат Резорт Ош",
    "name_en": "Jannat Resort Osh",
    "slug": "jannat-resort-osh",
    "about_ru": "Ресторан Жаннат Резорт в городе Ош. Изысканная кухня в уютной обстановке.",
    "about_ky": "Ош шаарындагы Жаннат Резорт ресторану. Ыңгайлуу чөйрөдө таасирдүү тамак-аш.",
    "about_en": "Jannat Resort restaurant in Osh city. Exquisite cuisine in a cozy atmosphere.",
}

BRANCH = {
    "name_ru": "Жаннат Резорт Ош",
    "name_ky": "Жаннат Резорт Ош",
    "name_en": "Jannat Resort Osh",
    "is_open_24h": False,
    "work_days": "0,1,2,3,4,5,6",
}

# Format: (name_ru, name_ky, name_en)
CATEGORIES = [
    ("Закуски", "Тамак-ашка чакыруу", "Appetizers"),
    ("Завтрак", "Эртең мененки тамак", "Breakfast"),
    ("Салаты", "Салаттар", "Salads"),
    ("Супы", "Шорполор", "Soups"),
    ("Паста", "Макарон", "Pasta"),
    ("Роллы", "Роллдор", "Rolls"),
    ("Пицца", "Пицца", "Pizza"),
    ("Бургеры", "Бургерлер", "Burgers"),
    ("Вторые блюда", "Экинчи тамактар", "Main Courses"),
    ("Блюда на гриле", "Грилде бышырылган тамактар", "Grilled Dishes"),
    ("Гарниры", "Гарнирлер", "Side Dishes"),
    ("Десерты", "Десерттер", "Desserts"),
    ("Кофе", "Кофе", "Coffee"),
    ("Чай", "Чай", "Tea"),
    ("Свежевыжатые соки", "Жаңы сыгылган ширелер", "Fresh Juices"),
]

# Format: (category_index, name_ru, name_ky, name_en, desc_ru, desc_ky, desc_en, price, image_search_query)
ITEMS = [
    # ── ЗАКУСКИ (0) ────────────────────────────────────────────────────────────
    (0, "Ассорти закусок", "Тамак-аш ассортиси", "Appetizer Assortment",
     "Микс из лучших закусок ресторана: мясное и сырное ассорти, овощи, соусы",
     "Мейкананын эң жакшы тамак-аштарынын аралашмасы: эт жана быштак ассортиси, жашылчалар, соустар",
     "A mix of the restaurant's best appetizers: meat and cheese assortment, vegetables, sauces",
     1190, "appetizer assortment platter mixed"),

    (0, "Брускетта мини-ассорти", "Брускетта мини-ассорти", "Bruschetta Mini Assortment",
     "Хрустящие тосты с разнообразными топпингами: помидоры, сыр, зелень, паштет",
     "Ар кандай топпингтер менен кытырак тосттор: помидор, быштак, жашылдыктар, паштет",
     "Crispy toasts with various toppings: tomatoes, cheese, herbs, pâté",
     1210, "bruschetta assortment tomato cheese"),

    (0, "Овощное ассорти", "Жашылча ассортиси", "Vegetable Assortment",
     "Свежие сезонные овощи, нарезанные и поданные с соусом",
     "Соус менен берилген жаңы мезгилдик жашылчалар",
     "Fresh seasonal vegetables sliced and served with sauce",
     590, "vegetable platter fresh assortment"),

    (0, "Сырное плато", "Быштак платосу", "Cheese Plate",
     "Ассорти из отборных сыров, подаётся с медом, грецким орехом и виноградом",
     "Бал, жаңгак жана жүзүм менен берилген тандалма быштактардын ассортиси",
     "Assortment of selected cheeses served with honey, walnuts and grapes",
     810, "cheese plate assortment honey nuts"),

    (0, "Овощная тарелка", "Жашылча табагы", "Vegetable Plate",
     "Свежие овощи на тарелке с зеленью и соусом",
     "Жашылдыктар жана соус менен табакта жаңы жашылчалар",
     "Fresh vegetables on a plate with herbs and sauce",
     620, "vegetable plate fresh herbs"),

    (0, "Рыбное ассорти", "Балык ассортиси", "Fish Assortment",
     "Ассорти из красной рыбы: семга, форель, тунец, икра, украшенные зеленью",
     "Кызыл балык ассортиси: семга, форель, тунец, икра, жашылдыктар менен кооздолгон",
     "Assortment of red fish: salmon, trout, tuna, caviar, garnished with greens",
     2190, "fish assortment salmon trout seafood platter"),

    (0, "Крылышки BBQ", "BBQ Канатчалары", "BBQ Wings",
     "Куриные крылышки в фирменном соусе BBQ, поданные с картофелем фри",
     "Картошке фри менен берилген өзгөчө BBQ соусундагы тоок канатчалары",
     "Chicken wings in signature BBQ sauce, served with french fries",
     810, "bbq chicken wings crispy fries"),

    (0, "Баклажаны фри", "Баклажан фри", "Fried Eggplant",
     "Хрустящие жареные баклажаны с чесноком и зеленью",
     "Сарымсак жана жашылдыктар менен кытырак куурулган баклажандар",
     "Crispy fried eggplant with garlic and herbs",
     790, "fried eggplant crispy garlic"),

    (0, "Мясная тарелка", "Эт табагы", "Meat Plate",
     "Ассорти из мясных деликатесов: колбасы, окорок, буженина, соусы",
     "Эт деликатестеринин ассортиси: колбасалар, чочко буту, буженина, соустар",
     "Assortment of meat delicacies: sausages, ham, boiled pork, sauces",
     1720, "meat charcuterie plate assortment"),

    # ── ЗАВТРАК (1) ────────────────────────────────────────────────────────────
    (1, "Фирменный завтрак «Жаннат»", "«Жаннат» Фирмалык Эртең Мененки", "Signature Breakfast «Jannat»",
     "Яичница, тосты, колбаса, сыр, масло, джем, свежие овощи, напиток на выбор",
     "Жумуртка, тосттор, колбаса, быштак, май, джем, жаңы жашылчалар, тандалма суусундук",
     "Scrambled eggs, toasts, sausage, cheese, butter, jam, fresh vegetables, choice of drink",
     620, "full breakfast eggs toast sausage"),

    (1, "Блины домашние", "Үй Блинчиктери", "Homemade Pancakes",
     "Тонкие блины по домашнему рецепту, подаются со сметаной и джемом",
     "Каймак жана джем менен берилген үй рецепти боюнча жука блинчиктер",
     "Thin pancakes made from a home recipe, served with sour cream and jam",
     180, "homemade pancakes thin cream jam"),

    (1, "Начинка для блинов", "Блинчик толтурмасы", "Pancake Filling",
     "Дополнительная начинка для блинов: варенье, мёд, шоколад или сгущёнка",
     "Блинчик үчүн кошумча толтурма: жем, бал, шоколад же кайнатылган конденсацияланган сүт",
     "Extra filling for pancakes: jam, honey, chocolate or condensed milk",
     150, "pancake filling jam honey chocolate"),

    (1, "Бельгийские вафли с мороженым", "Белгия Вафлилери Балмуздак Менен", "Belgian Waffles with Ice Cream",
     "Хрустящие бельгийские вафли со свежими ягодами и шариком мороженого",
     "Жаңы мөмөлөр жана балмуздак шары менен кытырак белгия вафлилери",
     "Crispy Belgian waffles with fresh berries and a scoop of ice cream",
     240, "belgian waffles ice cream berries"),

    (1, "Каша рисовая с карамелизированными яблоками", "Карамелдештирилген Алма Менен Күрүч Боткосу", "Rice Porridge with Caramelized Apples",
     "Нежная рисовая каша на молоке с карамелизированными яблоками и корицей",
     "Карамелдештирилген алма жана дарчын менен сүттүү назик күрүч боткосу",
     "Delicate rice porridge with milk, caramelized apples and cinnamon",
     220, "rice porridge caramelized apple cinnamon"),

    (1, "Каша овсяная с курагой", "Кургатылган Өрүк Менен Сулу Боткосу", "Oatmeal with Dried Apricots",
     "Овсяная каша на молоке с курагой, медом и орехами",
     "Кургатылган өрүк, бал жана жаңгак менен сүттүү сулу боткосу",
     "Oatmeal with milk, dried apricots, honey and nuts",
     200, "oatmeal dried apricots honey nuts"),

    (1, "Каша манная с ягодами", "Мөмөлөр Менен Манная Боткосу", "Semolina Porridge with Berries",
     "Нежная манная каша на молоке с ягодным соусом",
     "Мөмө соусу менен сүттүү назик манная боткосу",
     "Delicate semolina porridge with milk and berry sauce",
     210, "semolina porridge berries sauce"),

    (1, "Омлет классический", "Классикалык Омлет", "Classic Omelette",
     "Пышный омлет из 3 яиц с сыром, зеленью и овощами",
     "Быштак, жашылдыктар жана жашылчалар менен 3 жумурткадан жасалган пышный омлет",
     "Fluffy 3-egg omelette with cheese, herbs and vegetables",
     320, "classic omelette eggs cheese herbs"),

    (1, "Глазунья с овощами", "Жашылчалар Менен Глазунья", "Fried Eggs with Vegetables",
     "Яичница-глазунья с поджаренными овощами и зеленью",
     "Куурулган жашылчалар жана жашылдыктар менен глазунья",
     "Fried eggs with sautéed vegetables and herbs",
     320, "fried eggs vegetables sunny side up"),

    (1, "Ассорти колбас/сыры/овощи", "Колбаса/Быштак/Жашылча Ассортиси", "Assortment of Sausages/Cheese/Vegetables",
     "Нарезка из колбас, сыров и свежих овощей на тарелке",
     "Табакта колбасалардын, быштактардын жана жаңы жашылчалардын кесиндилери",
     "Sliced sausages, cheeses and fresh vegetables on a plate",
     90, "cold cuts cheese vegetables plate"),

    (1, "Сырники с ягодным соусом", "Мөмө Соусу Менен Сырниктер", "Cottage Cheese Pancakes with Berry Sauce",
     "Нежные сырники из творога с ванилью, подаются со свежим ягодным соусом",
     "Ваниль менен творогдон жасалган назик сырниктер, жаңы мөмө соусу менен берилет",
     "Delicate cottage cheese pancakes with vanilla, served with fresh berry sauce",
     320, "cottage cheese pancakes syrniki berry sauce"),

    # ── САЛАТЫ (2) ─────────────────────────────────────────────────────────────
    (2, "Фирменный салат «Жаннат»", "«Жаннат» Фирмалык Салаты", "Signature Salad «Jannat»",
     "Микс-салат, курица гриль, помидоры черри, авокадо, пармезан, фирменный дресинг",
     "Микс-салат, гриль тоок эти, черри помидору, авокадо, пармезан, өзгөчө дрессинг",
     "Mixed greens, grilled chicken, cherry tomatoes, avocado, parmesan, signature dressing",
     710, "signature salad grilled chicken avocado"),

    (2, "Салат с баклажанами", "Баклажан Салаты", "Eggplant Salad",
     "Запечённые баклажаны, помидоры, перец, чеснок, зелень, оливковое масло",
     "Бышырылган баклажандар, помидорлор, калемпир, сарымсак, жашылдыктар, зайтун майы",
     "Baked eggplant, tomatoes, bell pepper, garlic, herbs, olive oil",
     560, "eggplant salad roasted tomatoes"),

    (2, "Салат Греческий", "Грек Салаты", "Greek Salad",
     "Помидоры, огурцы, перец, маслины, сыр фета, оливковое масло, орегано",
     "Помидорлор, бадыраңдар, калемпир, зайтун, фета быштагы, зайтун майы, орегано",
     "Tomatoes, cucumbers, pepper, olives, feta cheese, olive oil, oregano",
     640, "greek salad feta olives tomatoes"),

    (2, "Цезарь с курицей", "Тоок Эти Менен Цезарь", "Caesar with Chicken",
     "Салат романо, курица гриль, гренки, пармезан, соус цезарь",
     "Романо салаты, гриль тоок эти, гренкилер, пармезан, цезарь соусу",
     "Romaine lettuce, grilled chicken, croutons, parmesan, caesar dressing",
     660, "caesar salad chicken croutons parmesan"),

    (2, "Салат с красной рыбой и яйцом-пашот", "Кызыл Балык Жана Пашот Жумуртка Менен Салат", "Salad with Red Fish and Poached Egg",
     "Микс-салат, семга, яйцо-пашот, авокадо, каперсы, лимонный дресинг",
     "Микс-салат, семга балыгы, пашот жумуртка, авокадо, каперс, лимон дрессинги",
     "Mixed greens, salmon, poached egg, avocado, capers, lemon dressing",
     880, "salad salmon poached egg avocado"),

    (2, "Теплый салат из говядины (острый)", "Жылуу Уй Эт Салаты (Ачуу)", "Warm Beef Salad (Spicy)",
     "Жареная говядина, микс-салат, перец чили, лук, соевый соус, кунжут",
     "Куурулган уй эти, микс-салат, чили калемпири, пияз, соя соусу, сейдана",
     "Fried beef, mixed greens, chili pepper, onion, soy sauce, sesame",
     680, "warm beef salad spicy asian"),

    (2, "Салат с древесными грибами", "Жыгач Козу Карындар Менен Салат", "Salad with Wood Mushrooms",
     "Древесные грибы, морковь по-корейски, зелень, кунжутный соус",
     "Жыгач козу карындары, кориялык сабиз, жашылдыктар, сейдана соусу",
     "Wood mushrooms, Korean-style carrots, herbs, sesame sauce",
     710, "wood mushrooms salad asian sesame"),

    (2, "Салат с авокадо и киноа", "Авокадо Жана Кино Менен Салат", "Salad with Avocado and Quinoa",
     "Киноа, авокадо, помидоры черри, огурцы, лимонный дресинг, семена чиа",
     "Кино, авокадо, черри помидору, бадыраңдар, лимон дрессинги, чиа уруктары",
     "Quinoa, avocado, cherry tomatoes, cucumbers, lemon dressing, chia seeds",
     780, "quinoa avocado salad healthy fresh"),

    (2, "Салат с курицей и нутом", "Тоок Эти Жана Нут Менен Салат", "Salad with Chicken and Chickpeas",
     "Курица гриль, нут, помидоры, огурцы, зелень, оливковое масло",
     "Гриль тоок эти, нут буурчак, помидорлор, бадыраңдар, жашылдыктар, зайтун майы",
     "Grilled chicken, chickpeas, tomatoes, cucumbers, herbs, olive oil",
     510, "chicken chickpea salad healthy"),

    (2, "Китайский салат с говяжьим языком", "Уй Тил Менен Кытай Салаты", "Chinese Salad with Beef Tongue",
     "Отварной говяжий язык, морковь, огурцы, чеснок, кунжутный соус, зелень",
     "Кайнатылган уй тили, сабиз, бадыраңдар, сарымсак, сейдана соусу, жашылдыктар",
     "Boiled beef tongue, carrots, cucumbers, garlic, sesame sauce, herbs",
     820, "beef tongue salad chinese sesame"),

    # ── СУПЫ (3) ───────────────────────────────────────────────────────────────
    (3, "Грибной крем-суп", "Козу Карын Крем-Шорпосу", "Mushroom Cream Soup",
     "Бархатистый крем-суп из шампиньонов со сливками и гренками",
     "Гренкилер жана каймак менен шампиньондордон жасалган жумшак крем-шорпо",
     "Velvety cream soup of champignons with cream and croutons",
     640, "mushroom cream soup champignon"),

    (3, "Суп-пюре с красной чечевицей", "Кызыл Мержимек Менен Суп-Пюре", "Red Lentil Cream Soup",
     "Нежный суп-пюре из красной чечевицы с пряностями и лимоном",
     "Татымалдар жана лимон менен кызыл мержимектен жасалган назик суп-пюре",
     "Delicate red lentil cream soup with spices and lemon",
     350, "red lentil soup cream puree"),

    (3, "Шорпо из баранины/говядины", "Кой/Уй Эти Менен Шорпо", "Lamb/Beef Shorpo",
     "Традиционный кыргызский суп из баранины или говядины с картофелем и овощами",
     "Картошке жана жашылчалар менен кой же уй этинен жасалган салт кыргыз шорпосу",
     "Traditional Kyrgyz soup with lamb or beef, potatoes and vegetables",
     610, "shorpo kyrgyz lamb beef soup traditional"),

    (3, "Рамен из говядины/сливочный/курицы", "Уй Эти/Каймак/Тоок Рамени", "Beef/Cream/Chicken Ramen",
     "Японский суп рамен с насыщенным бульоном, лапшой, мясом и яйцом",
     "Бай шорпо, лапша, эт жана жумуртка менен жапон рамен шорпосу",
     "Japanese ramen soup with rich broth, noodles, meat and egg",
     620, "ramen soup noodles egg broth japanese"),

    (3, "Окрошка из говядины", "Уй Эти Менен Окрошка", "Beef Okroshka",
     "Традиционная холодная окрошка с говядиной, овощами, квасом или кефиром",
     "Уй эти, жашылчалар, квас же кефир менен салт муздак окрошка",
     "Traditional cold okroshka with beef, vegetables, kvass or kefir",
     390, "okroshka cold soup beef vegetables"),

    (3, "Тыквенный суп", "Асканы Шорпосу", "Pumpkin Soup",
     "Нежный крем-суп из тыквы со сливками, семечками и имбирём",
     "Каймак, уруктар жана имбирь менен аскандан жасалган назик крем-шорпо",
     "Delicate pumpkin cream soup with cream, seeds and ginger",
     410, "pumpkin soup cream ginger"),

    (3, "Куриный суп-лапша по-домашнему", "Үйдөгүдөй Тоок Лапша Шорпосу", "Homestyle Chicken Noodle Soup",
     "Наваристый куриный бульон с домашней лапшой и овощами",
     "Үй лапшасы жана жашылчалар менен байлыктуу тоок шорпосу",
     "Rich chicken broth with homemade noodles and vegetables",
     460, "chicken noodle soup homestyle"),

    (3, "Тайский суп Том-ям", "Тай Том-ям Шорпосу", "Thai Tom Yum Soup",
     "Острый тайский суп с морепродуктами, грибами, лимонной травой и кокосовым молоком",
     "Деңиз азыктары, козу карындар, лимон чөбү жана кокос сүтү менен ачуу тай шорпосу",
     "Spicy Thai soup with seafood, mushrooms, lemongrass and coconut milk",
     860, "tom yum soup thai spicy seafood"),

    # ── ПАСТА (4) ──────────────────────────────────────────────────────────────
    (4, "Фетучинни с курицей и грибами", "Тоок Эти Жана Козу Карындар Менен Фетучинни", "Fettuccine with Chicken and Mushrooms",
     "Паста фетучини, курица, шампиньоны, сливочный соус, пармезан",
     "Фетучини макарону, тоок эти, шампиньон козу карындары, каймак соусу, пармезан",
     "Fettuccine pasta, chicken, champignons, cream sauce, parmesan",
     660, "fettuccine chicken mushroom cream sauce"),

    (4, "Спагетти с морепродуктами", "Деңиз Азыктары Менен Спагетти", "Spaghetti with Seafood",
     "Спагетти с мидиями, креветками, кальмарами в томатном или сливочном соусе",
     "Томат же каймак соусунда мидия, креветка, кальмар менен спагетти",
     "Spaghetti with mussels, shrimp, squid in tomato or cream sauce",
     1260, "spaghetti seafood mussels shrimp"),

    (4, "Паста с соусом «Песто»", "«Песто» Соусу Менен Паста", "Pasta with Pesto Sauce",
     "Паста пенне или фарфалле с классическим соусом песто, пармезаном и кедровыми орехами",
     "Классикалык песто соусу, пармезан жана кедр жаңгагы менен пенне же фарфалле паста",
     "Penne or farfalle pasta with classic pesto sauce, parmesan and pine nuts",
     720, "pasta pesto sauce pine nuts parmesan"),

    (4, "Фарфалле с семгой и брокколи", "Семга Жана Брокколи Менен Фарфалле", "Farfalle with Salmon and Broccoli",
     "Паста фарфалле, семга, брокколи, сливки, чеснок, пармезан",
     "Фарфалле паста, семга балыгы, брокколи, каймак, сарымсак, пармезан",
     "Farfalle pasta, salmon, broccoli, cream, garlic, parmesan",
     920, "farfalle salmon broccoli cream pasta"),

    (4, "Спагетти болоньезе", "Болоньезе Спагеттиси", "Spaghetti Bolognese",
     "Спагетти с мясным соусом болоньезе из говяжьего фарша, помидоров и пармезана",
     "Уй эти фарши, помидор жана пармезандан жасалган болоньезе эт соусу менен спагетти",
     "Spaghetti with bolognese meat sauce from ground beef, tomatoes and parmesan",
     860, "spaghetti bolognese meat sauce"),

    # ── РОЛЛЫ (5) ──────────────────────────────────────────────────────────────
    (5, "Филадельфия", "Филадельфия", "Philadelphia Roll",
     "Рис, нори, семга, сыр творожный, огурцы",
     "Күрүч, нори, семга балыгы, творожный быштак, бадыраңдар",
     "Rice, nori, salmon, cream cheese, cucumbers",
     660, "philadelphia roll salmon cream cheese classic"),

    (5, "Калифорния", "Калифорния", "California Roll",
     "Рис, нори, краб, авокадо, огурцы, тобико",
     "Күрүч, нори, краб, авокадо, бадыраңдар, тобико икрасы",
     "Rice, nori, crab, avocado, cucumbers, tobiko",
     1260, "california roll crab avocado tobiko"),

    (5, "Спринг роллы Цезарь", "Цезарь Спринг Роллдору", "Caesar Spring Rolls",
     "Рисовая бумага, курица гриль, листья романо, пармезан, соус цезарь",
     "Күрүч кагазы, гриль тоок эти, романо жалбырактары, пармезан, цезарь соусу",
     "Rice paper, grilled chicken, romaine lettuce, parmesan, caesar dressing",
     720, "spring rolls caesar chicken fresh"),

    (5, "Запеченные роллы Мистер крабс", "Мистер Крабс Бышырылган Роллдору", "Baked Rolls Mr. Krabs",
     "Рис, нори, краб, сливочный сыр, тобико, запеченные с майонезом и соусом",
     "Күрүч, нори, краб, каймак быштак, тобико, майонез жана соус менен бышырылган",
     "Rice, nori, crab, cream cheese, tobiko, baked with mayonnaise and sauce",
     920, "baked roll crab cream cheese"),

    (5, "Запеченные роллы Санта-Фе", "Санта-Фе Бышырылган Роллдору", "Baked Rolls Santa Fe",
     "Рис, нори, курица, перец, сливочный сыр, соус сальса, запеченные",
     "Күрүч, нори, тоок эти, калемпир, каймак быштак, сальса соусу, бышырылган",
     "Rice, nori, chicken, pepper, cream cheese, salsa sauce, baked",
     860, "baked roll chicken salsa pepper"),

    # ── ПИЦЦА (6) ──────────────────────────────────────────────────────────────
    (6, "Пепперони", "Пепперони", "Pepperoni Pizza",
     "Тесто, соус томатный, сыр Моцарелла, колбаса Пепперони",
     "Камыр, томат соусу, Моцарелла быштагы, Пепперони колбасасы",
     "Dough, tomato sauce, mozzarella cheese, pepperoni sausage",
     640, "pepperoni pizza classic mozzarella"),

    (6, "Пицца с ростбифом", "Ростбиф Менен Пицца", "Pizza with Roast Beef",
     "Тесто, соус, ростбиф из говядины, руккола, пармезан, помидоры черри",
     "Камыр, соус, уй этинен ростбиф, руккола, пармезан, черри помидору",
     "Dough, sauce, beef roast, arugula, parmesan, cherry tomatoes",
     860, "pizza roast beef arugula parmesan"),

    (6, "Капрезе", "Капрезе Пиццасы", "Caprese Pizza",
     "Тесто, томатный соус, сыр Моцарелла, свежие помидоры, базилик, оливковое масло",
     "Камыр, томат соусу, Моцарелла быштагы, жаңы помидорлор, райхан, зайтун майы",
     "Dough, tomato sauce, mozzarella cheese, fresh tomatoes, basil, olive oil",
     790, "caprese pizza margherita basil tomato"),

    (6, "Пицца 4 сыра", "4 Быштак Пиццасы", "Four Cheese Pizza",
     "Тесто, 4 вида сыра: Моцарелла, Горгонзола, Пармезан, Рикотта, соус",
     "Камыр, 4 түр быштак: Моцарелла, Горгонзола, Пармезан, Рикотта, соус",
     "Dough, 4 types of cheese: Mozzarella, Gorgonzola, Parmesan, Ricotta, sauce",
     840, "four cheese pizza quattro formaggi"),

    (6, "Пицца с курицей и грибами", "Тоок Эти Жана Козу Карындар Менен Пицца", "Pizza with Chicken and Mushrooms",
     "Тесто, соус сливочный, курица, шампиньоны, сыр Моцарелла",
     "Камыр, каймак соусу, тоок эти, шампиньон козу карындары, Моцарелла быштагы",
     "Dough, cream sauce, chicken, champignon mushrooms, mozzarella cheese",
     640, "chicken mushroom pizza cream sauce"),

    # ── БУРГЕРЫ (7) ────────────────────────────────────────────────────────────
    (7, "Бургер с фри", "Фри Менен Бургер", "Burger with Fries",
     "Говяжья котлета, булочка, листья салата, помидор, соус, картофель фри",
     "Уй этинен котлета, будка, салат жалбырактары, помидор, соус, картошке фри",
     "Beef patty, bun, lettuce, tomato, sauce, french fries",
     660, "beef burger fries classic"),

    (7, "Чизбургер с фри", "Фри Менен Чизбургер", "Cheeseburger with Fries",
     "Говяжья котлета, сыр чеддер, булочка, салат, помидор, соус, картофель фри",
     "Уй этинен котлета, чеддер быштагы, будка, салат, помидор, соус, картошке фри",
     "Beef patty, cheddar cheese, bun, lettuce, tomato, sauce, french fries",
     730, "cheeseburger cheddar fries classic"),

    (7, "Чикенбургер с фри", "Фри Менен Чикенбургер", "Chickenburger with Fries",
     "Куриная котлета гриль, булочка, листья салата, помидор, соус, картофель фри",
     "Гриль тоок котлетасы, будка, салат жалбырактары, помидор, соус, картошке фри",
     "Grilled chicken patty, bun, lettuce, tomato, sauce, french fries",
     510, "chicken burger fries grilled"),

    (7, "Чикенчизбургер с фри", "Фри Менен Чикенчизбургер", "Chicken Cheeseburger with Fries",
     "Куриная котлета, сыр, булочка, листья салата, помидор, соус, картофель фри",
     "Тоок котлетасы, быштак, будка, салат жалбырактары, помидор, соус, картошке фри",
     "Chicken patty, cheese, bun, lettuce, tomato, sauce, french fries",
     580, "chicken cheeseburger fries"),

    # ── ВТОРЫЕ БЛЮДА (8) ───────────────────────────────────────────────────────
    (8, "Томленные ребра говядина/баранина", "Уй/Кой Эти Кабыргалары Буштанды", "Braised Ribs Beef/Lamb",
     "Медленно томлёные рёбра говядины или баранины с соусом и гарниром",
     "Соус жана гарнир менен акырындык менен бышырылган уй же кой эти кабыргалары",
     "Slowly braised beef or lamb ribs with sauce and side dish",
     1190, "braised ribs beef lamb slow cooked"),

    (8, "Филе форели в сливочном соусе с рисом", "Каймак Соусунда Форель Филеси Күрүч Менен", "Trout Fillet in Cream Sauce with Rice",
     "Нежное филе форели в сливочном соусе с рисом и овощами",
     "Күрүч жана жашылчалар менен каймак соусунда назик форель филеси",
     "Delicate trout fillet in cream sauce with rice and vegetables",
     990, "trout fillet cream sauce rice"),

    (8, "Семга с рисом басмати", "Басмати Күрүч Менен Семга", "Salmon with Basmati Rice",
     "Стейк из семги на гриле с рисом басмати и соусом тартар",
     "Тартар соусу менен басмати күрүч менен гриль семга стейки",
     "Grilled salmon steak with basmati rice and tartar sauce",
     1320, "salmon steak basmati rice grilled"),

    (8, "Оссобуко из баранины по милански", "Миланча Кой Этинен Оссобуко", "Lamb Ossobuco Milanese",
     "Тушеная баранья голень по-милански с ризотто и гремолатой",
     "Ризотто жана гремолата менен миланча тушеланган кой этинин шыйрагы",
     "Braised lamb shank Milanese style with risotto and gremolata",
     1210, "ossobuco lamb milanese risotto"),

    (8, "Хрустящий куриный рулет с грибным соусом", "Козу Карын Соусу Менен Кытырак Тоок Рулети", "Crispy Chicken Roulade with Mushroom Sauce",
     "Рулет из куриного филе, запечённый до хрустящей корочки, с грибным соусом",
     "Козу карын соусу менен кытырак кабыкчасы болгонго чейин бышырылган тоок филесинен жасалган рулет",
     "Chicken fillet roulade baked to a crispy crust, with mushroom sauce",
     890, "chicken roulade crispy mushroom sauce"),

    (8, "Филе миньон с картофельным пюре", "Картошке Пюреси Менен Филе Миньон", "Filet Mignon with Mashed Potatoes",
     "Сочное филе миньон из говядины, поданное с нежным картофельным пюре и соусом",
     "Соус менен берилген картошке пюреси менен уй этинен назик филе миньон",
     "Juicy beef filet mignon served with creamy mashed potatoes and sauce",
     1290, "filet mignon beef mashed potatoes"),

    (8, "Бефстроганов из говядины", "Уй Этинен Бефстроганов", "Beef Stroganoff",
     "Нежные кусочки говядины в сливочно-грибном соусе, подаются с гарниром",
     "Гарнир менен берилген каймак-козу карын соусунда уй этинин назик кесиндилери",
     "Tender beef pieces in cream-mushroom sauce, served with side dish",
     710, "beef stroganoff cream mushroom sauce"),

    (8, "Баранья шея с фри", "Фри Менен Кой Мойну", "Lamb Neck with Fries",
     "Медленно приготовленная баранья шея с хрустящим картофелем фри",
     "Кытырак картошке фри менен акырындык менен бышырылган кой мойну",
     "Slowly cooked lamb neck with crispy french fries",
     990, "lamb neck fries slow cooked"),

    (8, "Картофель фри с мясом", "Эт Менен Картошке Фри", "French Fries with Meat",
     "Картофель фри с кусочками жареного мяса и соусом",
     "Соус менен куурулган эт кесиндилери менен картошке фри",
     "French fries with pieces of fried meat and sauce",
     780, "french fries meat sauce"),

    (8, "Куриные котлеты с пюре", "Пюре Менен Тоок Котлеталары", "Chicken Cutlets with Mashed Potatoes",
     "Нежные куриные котлеты с картофельным пюре и сливочным соусом",
     "Картошке пюреси жана каймак соусу менен назик тоок котлеталары",
     "Tender chicken cutlets with mashed potatoes and cream sauce",
     490, "chicken cutlets mashed potato cream"),

    (8, "Кесадилья с куриным филе и соусом сальса", "Тоок Филеси Жана Сальса Соусу Менен Кесадилья", "Quesadilla with Chicken Fillet and Salsa",
     "Мексиканская кесадилья с куриным филе, перцем, сыром и соусом сальса",
     "Тоок филеси, калемпир, быштак жана сальса соусу менен мексикандык кесадилья",
     "Mexican quesadilla with chicken fillet, pepper, cheese and salsa sauce",
     680, "quesadilla chicken cheese salsa mexican"),

    (8, "Куурдак из говядины/баранины", "Уй/Кой Этинен Куурдак", "Kuurdaq from Beef/Lamb",
     "Традиционное кыргызское блюдо — жареное мясо с луком и специями",
     "Пияз жана татымалдар менен куурулган эт — салт кыргыз тамагы",
     "Traditional Kyrgyz dish — fried meat with onion and spices",
     910, "kuurdaq kyrgyz fried meat traditional"),

    (8, "Бешбармак из баранины", "Кой Этинен Бешбармак", "Beshbarmak from Lamb",
     "Традиционное кыргызское блюдо — отварная баранина с домашней лапшой и луком",
     "Кайнатылган кой эти, үй лапшасы жана пияз менен салт кыргыз тамагы",
     "Traditional Kyrgyz dish — boiled lamb with homemade pasta and onion",
     850, "beshbarmak kyrgyz lamb noodles traditional"),

    # ── БЛЮДА НА ГРИЛЕ (9) ─────────────────────────────────────────────────────
    (9, "Стейк тибон", "Тибон Стейки", "T-Bone Steak",
     "Стейк Т-образной кости, средней прожарки, с соусом и гарниром на гриле",
     "Гриль соус жана гарнир менен орточо куурулган Т-сөөк стейки",
     "T-bone steak, medium doneness, with sauce and grilled side dish",
     1510, "t-bone steak grilled restaurant medium"),

    (9, "Ковбой стейк", "Ковбой Стейки", "Cowboy Steak",
     "Массивный стейк из говядины на кости, поданный с соусом барбекю и гарниром",
     "Барбекю соусу жана гарнир менен берилген сөөктүү уй этинен массивдүү стейк",
     "Massive bone-in beef steak, served with BBQ sauce and side dish",
     1780, "cowboy steak bone in beef bbq"),

    (9, "Стейк рибай", "Рибай Стейки", "Ribeye Steak",
     "Мраморный стейк рибай из отборной говядины, поданный с соусом и гарниром",
     "Соус жана гарнир менен берилген тандалма уй этинен мрамор рибай стейки",
     "Marbled ribeye steak from premium beef, served with sauce and side dish",
     1930, "ribeye steak marbled premium grilled"),

    # ── ГАРНИРЫ (10) ───────────────────────────────────────────────────────────
    (10, "Картофель фри", "Картошке Фри", "French Fries",
     "Хрустящий картофель фри с солью",
     "Туз менен кытырак картошке фри",
     "Crispy french fries with salt",
     190, "french fries crispy golden"),

    (10, "Рис на пару", "Буулатылган Күрүч", "Steamed Rice",
     "Нежный рис на пару, сваренный до мягкости",
     "Жумшак болгонго чейин бышырылган назик буулатылган күрүч",
     "Delicate steamed rice, cooked until tender",
     120, "steamed rice white bowl"),

    (10, "Овощи на гриле", "Гриль Жашылчалары", "Grilled Vegetables",
     "Сезонные овощи, приготовленные на гриле с оливковым маслом и зеленью",
     "Зайтун майы жана жашылдыктар менен грильде бышырылган мезгилдик жашылчалар",
     "Seasonal vegetables grilled with olive oil and herbs",
     330, "grilled vegetables mixed zucchini pepper"),

    (10, "Картофель по-деревенски", "Кыштак Картошкесу", "Country-Style Potatoes",
     "Картофель, запечённый в духовке с травами и чесноком",
     "Чөп-чар жана сарымсак менен пешта бышырылган картошке",
     "Oven-baked potatoes with herbs and garlic",
     190, "country potato wedges oven baked"),

    # ── ДЕСЕРТЫ (11) ───────────────────────────────────────────────────────────
    (11, "Чизкейк", "Чизкейк", "Cheesecake",
     "Нежный чизкейк из сливочного сыра на песочной основе с ягодным соусом",
     "Мөмө соусу менен кум кысмага жасалган каймак быштактан назик чизкейк",
     "Delicate cheesecake made from cream cheese on a shortcrust base with berry sauce",
     320, "cheesecake cream berry sauce classic"),

    (11, "Фруктовое ассорти", "Жемиш Ассортиси", "Fruit Assortment",
     "Свежие сезонные фрукты, нарезанные и красиво поданные на тарелке",
     "Табакта сулуу берилген жаңы мезгилдик жемиштер",
     "Fresh seasonal fruits, sliced and beautifully presented on a plate",
     720, "fruit assortment fresh plate seasonal"),

    (11, "Тирамису", "Тирамису", "Tiramisu",
     "Классический итальянский десерт тирамису с маскарпоне и кофе",
     "Маскарпоне жана кофе менен классикалык италиялык тирамису десерти",
     "Classic Italian tiramisu dessert with mascarpone and coffee",
     440, "tiramisu classic italian mascarpone"),

    (11, "Прага", "Прага Торту", "Prague Cake",
     "Классический торт Прага с шоколадным кремом и шоколадной глазурью",
     "Шоколад крем жана шоколад глазурь менен классикалык Прага торт",
     "Classic Prague chocolate cake with chocolate cream and glaze",
     320, "prague chocolate cake classic"),

    (11, "Мороженое в ассортименте", "Ар Кандай Балмуздак", "Ice Cream Assortment",
     "Несколько шариков мороженого разных вкусов на выбор",
     "Тандалган ар кандай даамдагы бир нече шар балмуздак",
     "Several scoops of ice cream in various flavors of your choice",
     280, "ice cream scoops assortment colorful"),

    # ── КОФЕ (12) ──────────────────────────────────────────────────────────────
    (12, "Эспрессо", "Эспрессо", "Espresso",
     "Классический итальянский эспрессо из зёрен арабики",
     "Арабика ийне-жалбырактарынан классикалык итальялык эспрессо",
     "Classic Italian espresso from arabica beans",
     180, "espresso coffee shot classic"),

    (12, "Двойной эспрессо", "Кош Эспрессо", "Double Espresso",
     "Двойная порция классического эспрессо",
     "Классикалык эспрессонун эки порциясы",
     "Double shot of classic espresso",
     220, "double espresso two shots coffee"),

    (12, "Американо", "Американо", "Americano",
     "Эспрессо с горячей водой, мягкий и ароматный",
     "Ысык суу менен эспрессо, жумшак жана жытты",
     "Espresso with hot water, mild and aromatic",
     210, "americano coffee black cup"),

    (12, "Латте", "Латте", "Latte",
     "Эспрессо с большим количеством взбитого молока и молочной пеной",
     "Эспрессо көп жутулган сүт жана сүт көбүгү менен",
     "Espresso with a large amount of steamed milk and milk foam",
     240, "latte coffee milk foam"),

    (12, "Капучино", "Капучино", "Cappuccino",
     "Эспрессо, взбитое молоко и молочная пена в равных частях",
     "Тең бөлүктөрдө эспрессо, жутулган сүт жана сүт көбүгү",
     "Espresso, steamed milk and milk foam in equal parts",
     240, "cappuccino coffee foam classic"),

    (12, "Бейлиз кофе", "Бейлиз Кофе", "Baileys Coffee",
     "Кофе с ирландским ликером Baileys и взбитыми сливками",
     "Ирландиялык Baileys ликери жана камкайманы менен кофе",
     "Coffee with Irish Baileys liqueur and whipped cream",
     390, "baileys coffee cream liqueur"),

    (12, "Айриш кофе", "Айриш Кофе", "Irish Coffee",
     "Горячий кофе с ирландским виски и взбитыми сливками",
     "Ирландиялык виски жана камкайман менен ысык кофе",
     "Hot coffee with Irish whiskey and whipped cream",
     450, "irish coffee whiskey cream"),

    (12, "Сиропы к кофе", "Кофего Сироп", "Coffee Syrups",
     "Ароматные сиропы для добавления в кофе: ваниль, карамель, лесной орех и другие",
     "Кофеге кошуу үчүн жытты сироптор: ваниль, карамель, жаңгак жана башкалар",
     "Flavored syrups to add to coffee: vanilla, caramel, hazelnut and others",
     70, "coffee syrups vanilla caramel bottles"),

    # ── ЧАЙ (13) ───────────────────────────────────────────────────────────────
    (13, "Черный/зеленый чай", "Кара/Жашыл Чай", "Black/Green Tea",
     "Классический черный или зеленый чай в чайнике",
     "Чайнекте классикалык кара же жашыл чай",
     "Classic black or green tea in a teapot",
     120, "black green tea teapot classic"),

    (13, "Облепиховый чай", "Чоку Чай", "Sea Buckthorn Tea",
     "Согревающий облепиховый чай с медом и лимоном",
     "Бал жана лимон менен жылытуучу чоку чайы",
     "Warming sea buckthorn tea with honey and lemon",
     290, "sea buckthorn tea orange warm"),

    (13, "Имбирный чай", "Имбирь Чайы", "Ginger Tea",
     "Имбирный чай с лимоном и медом, согревает и тонизирует",
     "Лимон жана бал менен имбирь чайы, жылытат жана тонуслайт",
     "Ginger tea with lemon and honey, warms and tones",
     290, "ginger lemon honey tea warm"),

    (13, "Фруктовый чай", "Жемиш Чайы", "Fruit Tea",
     "Ароматный фруктовый чай из ягод и фруктов",
     "Мөмөлөр жана жемиштерден жасалган жытты жемиш чайы",
     "Aromatic fruit tea made from berries and fruits",
     290, "fruit tea berries colorful"),

    # ── СВЕЖЕВЫЖАТЫЕ СОКИ (14) ─────────────────────────────────────────────────
    (14, "Апельсиновый сок", "Апельсин Ширеси", "Orange Juice",
     "Свежевыжатый апельсиновый сок",
     "Жаңы сыгылган апельсин ширеси",
     "Freshly squeezed orange juice",
     320, "fresh squeezed orange juice glass"),

    (14, "Яблочный/Морковный/Яблочно-морковный сок", "Алма/Сабиз/Алма-Сабиз Ширеси", "Apple/Carrot/Apple-Carrot Juice",
     "Свежевыжатый сок из яблок, моркови или их смеси",
     "Алма, сабиздан же алардын аралашмасынан жаңы сыгылган ширеси",
     "Freshly squeezed juice from apples, carrots or their blend",
     280, "fresh juice apple carrot healthy"),
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
    help = "Import Jannat Resort Osh restaurant with full menu from аля кард 2026.pdf"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Parse only, do NOT write to DB")
        parser.add_argument("--no-images", action="store_true",
                            help="Skip image downloads")
        parser.add_argument("--reset", action="store_true",
                            help="Delete existing Jannat Resort restaurant and reimport")
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
        self.log(f"🍽  Жаннат Резорт Ош menu import")
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
