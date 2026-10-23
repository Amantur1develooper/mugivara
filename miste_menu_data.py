# -*- coding: utf-8 -*-
"""Меню кафе «Мисте» (Ош) на трёх языках.

Источник: сайт заведения miste.kg — названия, цены, составы и фото блюд.
Переводы и единый словарь ингредиентов подготовлены для Webordo.
"""

RESTAURANT = {
    "slug": "miste",
    "ru": "Мисте", "ky": "Мисте", "en": "Miste",
    "about_ru": "Кафе в Оше: завтраки, супы, горячее, пицца и бургеры. Тёплая атмосфера и вкусы природы.",
    "external_url": "https://miste.kg/",
}

BRANCHES = [
    {"ru": "Мисте — Ош", "ky": "Мисте — Ош", "en": "Miste — Osh",
     "address": "Салиева 27/5, Ош", "phone": "+996 226 600 800",
     "open_time": "09:00", "close_time": "00:00"},
]

CATEGORIES = [
    {
        "slug": "breakfast",
        "photo": "breakfast.webp",
        "ru": "Завтраки", "ky": "Эртең мененки тамак", "en": "Breakfasts",
        "items": [
            {
                "ru": "Английский завтрак",
                "ky": "Англис эртең мененки тамагы", "en": "English Breakfast",
                "d_ru": "Яйцо, колбаски охотничьи, помидоры, тостовый хлеб, микс салата, фасоль красная.", "d_ky": "Жумуртка, мергенче колбаскалар, помидор, тост наны, салат микси, кызыл буурчак.", "d_en": "Egg, hunter's sausages, tomatoes, toast bread, mixed greens, red beans.",
                "price": 325, "photo": "125887631922.webp",
            },
            {
                "ru": "Шакшука",
                "ky": "Шакшука", "en": "Shakshuka",
                "d_ru": "Яйцо, помидоры, фасоль красная, тостовый хлеб, перец болгарский.", "d_ky": "Жумуртка, помидор, кызыл буурчак, тост наны, болгар калемпири.", "d_en": "Egg, tomatoes, red beans, toast bread, bell pepper.",
                "price": 295, "photo": "972251705622.webp",
            },
            {
                "ru": "Омлет",
                "ky": "Омлет", "en": "Omelette",
                "d_ru": "Яйцо, молоко, микс салата, тостовый хлеб, крем-чиз.", "d_ky": "Жумуртка, сүт, салат микси, тост наны, крем-чиз.", "d_en": "Egg, milk, mixed greens, toast bread, cream cheese.",
                "price": 225, "photo": "567467869352.webp",
            },
            {
                "ru": "Глазунья",
                "ky": "Куурулган жумуртка", "en": "Fried Eggs",
                "d_ru": "Яйцо, тостовый хлеб, микс салата, бальзамический крем.", "d_ky": "Жумуртка, тост наны, салат микси, бальзамик креми.", "d_en": "Egg, toast bread, mixed greens, balsamic glaze.",
                "price": 205, "photo": "665386118452.webp",
            },
            {
                "ru": "Тост с лососем",
                "ky": "Кызыл балык менен тост", "en": "Toast with Salmon",
                "d_ru": "Тостовый хлеб, микс салата, сёмга слабосолёная, соус голландез, яйцо пашот, икра красная.", "d_ky": "Тост наны, салат микси, аз туздалган сёмга, голландез соусу, пашот жумуртка, кызыл уурпа.", "d_en": "Toast bread, mixed greens, lightly salted salmon, hollandaise sauce, poached egg, red caviar.",
                "price": 375, "photo": "593243241612.webp",
            },
            {
                "ru": "Сырники со сметаной и джемом",
                "ky": "Сырник каймак жана кыям менен", "en": "Syrniki with Sour Cream and Jam",
                "d_ru": "Творог, сметана, джем.", "d_ky": "Сүзмө, каймак, кыям.", "d_en": "Curd, sour cream, jam.",
                "price": 205, "photo": "102076050692.webp",
            },
            {
                "ru": "Каша рисовая с яблокой и фисташкой",
                "ky": "Алма жана фисташка менен күрүч ботко", "en": "Rice Porridge with Apple and Pistachio",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 155, "photo": "",
            },
            {
                "ru": "Каша овсяная с бананом и кешью",
                "ky": "Банан жана кешью менен сулу ботко", "en": "Oat Porridge with Banana and Cashew",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 195, "photo": "",
            },
        ],
    },
    {
        "slug": "salads",
        "photo": "salads.webp",
        "ru": "Салаты", "ky": "Салаттар", "en": "Salads",
        "items": [
            {
                "ru": "Фирменный салат “Мисте”",
                "ky": "«Мисте» фирмалык салаты", "en": "Signature Salad «Miste»",
                "d_ru": "Форель, апельсин, банан в кляре, брокколи, заправка апельсиновая.", "d_ky": "Форель, апельсин, кляр ичиндеги банан, брокколи, апельсин соусу.", "d_en": "Trout, orange, battered banana, broccoli, orange dressing.",
                "price": 475, "photo": "809063637762.webp",
            },
            {
                "ru": "Цезарь",
                "ky": "Цезарь", "en": "Caesar",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 345, "photo": "644639147062.webp",
            },
            {
                "ru": "Баклажан в кляре",
                "ky": "Кляр ичиндеги баклажан", "en": "Battered Eggplant",
                "d_ru": "Баклажан, помидоры, крем-чиз, заправка для баклажанов, кинза.", "d_ky": "Баклажан, помидор, крем-чиз, баклажан соусу, кинза.", "d_en": "Eggplant, tomatoes, cream cheese, eggplant dressing, cilantro.",
                "price": 325, "photo": "444661453022.webp",
            },
            {
                "ru": "Острый салат",
                "ky": "Ачуу салат", "en": "Spicy Salad",
                "d_ru": "Говядина, огурцы, перец болгарский, помидоры, лук красный, соус соевый.", "d_ky": "Уй эти, бадыраң, болгар калемпири, помидор, кызыл пияз, соя соусу.", "d_en": "Beef, cucumbers, bell pepper, tomatoes, red onion, soy sauce.",
                "price": 355, "photo": "",
            },
            {
                "ru": "Греческий салат с сыром халлуми",
                "ky": "Халлуми сыры менен грек салаты", "en": "Greek Salad with Halloumi",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 345, "photo": "491148085482.webp",
            },
        ],
    },
    {
        "slug": "soups",
        "photo": "soups.webp",
        "ru": "Супы", "ky": "Шорполор", "en": "Soups",
        "items": [
            {
                "ru": "Том Ям",
                "ky": "Том Ям", "en": "Tom Yum",
                "d_ru": "Форель, креветки, судак, шампиньоны, рис, молоко кокосовое, лайм.", "d_ky": "Форель, креветкалар, судак, шампиньон, күрүч, кокос сүтү, лайм.", "d_en": "Trout, shrimp, pike-perch, champignons, rice, coconut milk, lime.",
                "price": 525, "photo": "994776694642.webp",
            },
            {
                "ru": "Рамен с курицей",
                "ky": "Тоок менен рамен", "en": "Chicken Ramen",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 355, "photo": "273454413802.webp",
            },
            {
                "ru": "Рамен с говядиной",
                "ky": "Уй эти менен рамен", "en": "Beef Ramen",
                "d_ru": "Лапша, говядина, яйцо, сыр чеддер, нори, лук зелёный, соус кимчи.", "d_ky": "Кесме, уй эти, жумуртка, чеддер сыры, нори, жашыл пияз, кимчи соусу.", "d_en": "Noodles, beef, egg, cheddar, nori, spring onion, kimchi sauce.",
                "price": 385, "photo": "264539707112.webp",
            },
            {
                "ru": "Уха",
                "ky": "Балык шорпо", "en": "Fish Soup",
                "d_ru": "Судак, лосось, бульон рыбный, сливки, морковь, картофель, лук репчатый.", "d_ky": "Судак, кызыл балык, балык сорпосу, каймак, сабиз, картошка, пияз.", "d_en": "Pike-perch, salmon, fish broth, cream, carrot, potato, onion.",
                "price": 325, "photo": "581008735452.webp",
            },
            {
                "ru": "Тыквенный крем суп с сыром страчателла",
                "ky": "Страчателла менен ашкабак крем-шорпосу", "en": "Pumpkin Cream Soup with Stracciatella",
                "d_ru": "Тыква, сыр страчателла, лук репчатый, морковь, мёд, сливки.", "d_ky": "Ашкабак, страчателла сыры, пияз, сабиз, бал, каймак.", "d_en": "Pumpkin, stracciatella, onion, carrot, honey, cream.",
                "price": 275, "photo": "740017888122.webp",
            },
            {
                "ru": "Куриный суп с лапшой",
                "ky": "Кесме менен тоок шорпосу", "en": "Chicken Noodle Soup",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 295, "photo": "788857170752.webp",
            },
            {
                "ru": "Чечевичный крем суп",
                "ky": "Жасмык крем-шорпосу", "en": "Lentil Cream Soup",
                "d_ru": "Чечевица, картофель, морковь, лук репчатый, сливки.", "d_ky": "Жасмык, картошка, сабиз, пияз, каймак.", "d_en": "Lentils, potato, carrot, onion, cream.",
                "price": 265, "photo": "379695971882.webp",
            },
            {
                "ru": "Говяжий суп",
                "ky": "Уй эт шорпосу", "en": "Beef Soup",
                "d_ru": "Рёбра говяжьи, перец болгарский, морковь, лук репчатый, картофель.", "d_ky": "Уй кабыргасы, болгар калемпири, сабиз, пияз, картошка.", "d_en": "Beef ribs, bell pepper, carrot, onion, potato.",
                "price": 355, "photo": "531286038362.webp",
            },
        ],
    },
    {
        "slug": "hot",
        "photo": "hot.webp",
        "ru": "Горячие блюда", "ky": "Ысык тамактар", "en": "Hot Dishes",
        "items": [
            {
                "ru": "Куурдак с бараниной",
                "ky": "Кой эти менен куурдак", "en": "Kuurdak with Lamb",
                "d_ru": "Баранина, картофель, лук репчатый, укроп, пиде.", "d_ky": "Кой эти, картошка, пияз, укроп, пиде.", "d_en": "Lamb, potato, onion, dill, pide bread.",
                "price": 575, "photo": "767733475212.webp",
            },
            {
                "ru": "Куурдак с говядиной",
                "ky": "Уй эти менен куурдак", "en": "Kuurdak with Beef",
                "d_ru": "Говядина, картофель, лук репчатый, укроп, пиде.", "d_ky": "Уй эти, картошка, пияз, укроп, пиде.", "d_en": "Beef, potato, onion, dill, pide bread.",
                "price": 575, "photo": "472275547122.webp",
            },
            {
                "ru": "Стейк с лососем",
                "ky": "Кызыл балык стейги", "en": "Salmon Steak",
                "d_ru": "Лосось, соус сливочно-икорный, пюре из цветной капусты, микс салата, лимон.", "d_ky": "Кызыл балык, каймак-уурпа соусу, гүлдүү капуста пюреси, салат микси, лимон.", "d_en": "Salmon, creamy caviar sauce, cauliflower purée, mixed greens, lemon.",
                "price": 795, "photo": "857406233122.webp",
            },
            {
                "ru": "Форель в сливочном соусе",
                "ky": "Каймак соусундагы форель", "en": "Trout in Cream Sauce",
                "d_ru": "Форель, рис, перец болгарский, помидоры, сливки, микс салата.", "d_ky": "Форель, күрүч, болгар калемпири, помидор, каймак, салат микси.", "d_en": "Trout, rice, bell pepper, tomatoes, cream, mixed greens.",
                "price": 535, "photo": "231660007832.webp",
            },
            {
                "ru": "Бефстроганов с говядиной",
                "ky": "Уй эти менен бефстроганов", "en": "Beef Stroganoff",
                "d_ru": "Говядина, шампиньоны, лук репчатый, сметана, сливки, картофельное пюре, огурцы маринованные.", "d_ky": "Уй эти, шампиньон, пияз, каймак, каймак, картошка пюреси, маринадталган бадыраң.", "d_en": "Beef, champignons, onion, sour cream, cream, mashed potato, pickles.",
                "price": 515, "photo": "691034978872.webp",
            },
            {
                "ru": "Фри с мясом",
                "ky": "Эт менен фри", "en": "Fries with Beef",
                "d_ru": "Картофель фри, говядина, перец болгарский, лук зелёный, лук репчатый, кинза.", "d_ky": "Фри картошка, уй эти, болгар калемпири, жашыл пияз, пияз, кинза.", "d_en": "French fries, beef, bell pepper, spring onion, onion, cilantro.",
                "price": 465, "photo": "140075321242.webp",
            },
            {
                "ru": "Говяжий ребра в соусе BBQ",
                "ky": "BBQ соусундагы уй кабыргасы", "en": "Beef Ribs in BBQ Sauce",
                "d_ru": "Рёбра говяжьи, соус BBQ, картофель мини, розмарин.", "d_ky": "Уй кабыргасы, BBQ соусу, кичине картошка, розмарин.", "d_en": "Beef ribs, BBQ sauce, baby potatoes, rosemary.",
                "price": 695, "photo": "134474060562.webp",
            },
            {
                "ru": "Фрикасе с курицей",
                "ky": "Тоок менен фрикасе", "en": "Chicken Fricassee",
                "d_ru": "Куриное филе, перец болгарский, лук репчатый, сметана, сливки, рис, микс салата.", "d_ky": "Тоок филеси, болгар калемпири, пияз, каймак, каймак, күрүч, салат микси.", "d_en": "Chicken fillet, bell pepper, onion, sour cream, cream, rice, mixed greens.",
                "price": 395, "photo": "266957136542.webp",
            },
            {
                "ru": "Спагетти болоньезе",
                "ky": "Болоньезе спагетти", "en": "Spaghetti Bolognese",
                "d_ru": "Спагетти, фарш болоньезе, масло сливочное, сыр пармезан.", "d_ky": "Спагетти, болоньезе фаршы, сары май, пармезан сыры.", "d_en": "Spaghetti, bolognese sauce, butter, parmesan.",
                "price": 445, "photo": "595596598952.webp",
            },
            {
                "ru": "Удон",
                "ky": "Удон", "en": "Udon",
                "d_ru": "Лапша удон, говядина, кабачки, фасоль стручковая, перец болгарский, соус азиатский.", "d_ky": "Удон кесмеси, уй эти, кабак, кыналуу буурчак, болгар калемпири, азия соусу.", "d_en": "Udon noodles, beef, zucchini, green beans, bell pepper, asian sauce.",
                "price": 375, "photo": "798712088732.webp",
            },
            {
                "ru": "Соба с овощами",
                "ky": "Жашылча менен соба", "en": "Soba with Vegetables",
                "d_ru": "Лапша соба, перец болгарский, лук репчатый, лук красный, кабачки, фасоль стручковая, соус азиатский.", "d_ky": "Соба кесмеси, болгар калемпири, пияз, кызыл пияз, кабак, кыналуу буурчак, азия соусу.", "d_en": "Soba noodles, bell pepper, onion, red onion, zucchini, green beans, asian sauce.",
                "price": 365, "photo": "663762726962.webp",
            },
        ],
    },
    {
        "slug": "pizza",
        "photo": "pizza.webp",
        "ru": "Пицца", "ky": "Пицца", "en": "Pizza",
        "items": [
            {
                "ru": "Пеперони",
                "ky": "Пепперони", "en": "Pepperoni",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 535, "photo": "943631894432.webp",
            },
            {
                "ru": "Четыре сезона",
                "ky": "Төрт мезгил", "en": "Four Seasons",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 515, "photo": "706308090712.webp",
            },
            {
                "ru": "Пицца с курицей",
                "ky": "Тоок менен пицца", "en": "Pizza with Chicken",
                "d_ru": "Шампиньоны, куриное филе, сыр моцарелла, сыр пармезан.", "d_ky": "Шампиньон, тоок филеси, моцарелла сыры, пармезан сыры.", "d_en": "Champignons, chicken fillet, mozzarella, parmesan.",
                "price": 495, "photo": "952350118612.webp",
            },
            {
                "ru": "Пицца с тунцом",
                "ky": "Тунец менен пицца", "en": "Pizza with Tuna",
                "d_ru": "Сыр моцарелла, тунец, сыр пармезан.", "d_ky": "Моцарелла сыры, тунец, пармезан сыры.", "d_en": "Mozzarella, tuna, parmesan.",
                "price": 525, "photo": "837860287512.webp",
            },
            {
                "ru": "Фокачча",
                "ky": "Фокачча", "en": "Focaccia",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 95, "photo": "185237059932.webp",
            },
        ],
    },
    {
        "slug": "burgers",
        "photo": "burgers.webp",
        "ru": "Бургеры", "ky": "Бургерлер", "en": "Burgers",
        "items": [
            {
                "ru": "Классический бургер",
                "ky": "Классикалык бургер", "en": "Classic Burger",
                "d_ru": "Котлета говяжья, соус бургерный, салат айсберг, помидоры, лук красный, огурцы маринованные, картофель фри, кетчуп.", "d_ky": "Уй эт котлети, бургер соусу, айсберг салаты, помидор, кызыл пияз, маринадталган бадыраң, фри картошка, кетчуп.", "d_en": "Beef patty, burger sauce, iceberg lettuce, tomatoes, red onion, pickles, french fries, ketchup.",
                "price": 345, "photo": "509993422592.webp",
            },
            {
                "ru": "BBQ бургер с курицей",
                "ky": "Тоок менен BBQ бургер", "en": "BBQ Chicken Burger",
                "d_ru": "Куриное бедро, соус BBQ, соус сырный, салат айсберг, помидоры, огурцы маринованные, лук красный, картофель фри, кетчуп.", "d_ky": "Тоок саны, BBQ соусу, сыр соусу, айсберг салаты, помидор, маринадталган бадыраң, кызыл пияз, фри картошка, кетчуп.", "d_en": "Chicken thigh, BBQ sauce, cheese sauce, iceberg lettuce, tomatoes, pickles, red onion, french fries, ketchup.",
                "price": 335, "photo": "567468918402.webp",
            },
            {
                "ru": "Чизбургер",
                "ky": "Чизбургер", "en": "Cheeseburger",
                "d_ru": "Котлета говяжья, соус бургерный, сыр чеддер, салат айсберг, помидоры, огурцы маринованные, лук репчатый, картофель фри, кетчуп.", "d_ky": "Уй эт котлети, бургер соусу, чеддер сыры, айсберг салаты, помидор, маринадталган бадыраң, пияз, фри картошка, кетчуп.", "d_en": "Beef patty, burger sauce, cheddar, iceberg lettuce, tomatoes, pickles, onion, french fries, ketchup.",
                "price": 365, "photo": "875940537912.webp",
            },
            {
                "ru": "Наггетсы 6шт",
                "ky": "Наггетс 6 даана", "en": "Nuggets, 6 pcs",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 195, "photo": "764036707002.webp",
            },
            {
                "ru": "Наггетсы 12шт",
                "ky": "Наггетс 12 даана", "en": "Nuggets, 12 pcs",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 295, "photo": "521568135382.webp",
            },
        ],
    },
    {
        "slug": "bowls",
        "photo": "bowls.webp",
        "ru": "Боулы и поке", "ky": "Боул жана поке", "en": "Bowls & Poke",
        "items": [
            {
                "ru": "Боул",
                "ky": "Боул", "en": "Bowl",
                "d_ru": "Куриное филе, огурцы, помидоры, микс салата, фасоль красная, кукуруза, рис, яйцо.", "d_ky": "Тоок филеси, бадыраң, помидор, салат микси, кызыл буурчак, жүгөрү, күрүч, жумуртка.", "d_en": "Chicken fillet, cucumbers, tomatoes, mixed greens, red beans, corn, rice, egg.",
                "price": 365, "photo": "138847339452.webp",
            },
            {
                "ru": "Поке",
                "ky": "Поке", "en": "Poke",
                "d_ru": "Лосось слабосолёный, чука, яйцо пашот, брокколи, кукуруза, огурцы, рис.", "d_ky": "Аз туздалган кызыл балык, чука, пашот жумуртка, брокколи, жүгөрү, бадыраң, күрүч.", "d_en": "Lightly salted salmon, chuka salad, poached egg, broccoli, corn, cucumbers, rice.",
                "price": 445, "photo": "322418110442.webp",
            },
            {
                "ru": "Судак с пюре из цветной капусты",
                "ky": "Гүлдүү капуста пюреси менен судак", "en": "Pike-Perch with Cauliflower Purée",
                "d_ru": "Филе судака, капуста цветная, лимон, соус сливочно-икорный.", "d_ky": "Судак филеси, гүлдүү капуста, лимон, каймак-уурпа соусу.", "d_en": "Pike-perch fillet, cauliflower, lemon, creamy caviar sauce.",
                "price": 435, "photo": "411928306612.webp",
            },
        ],
    },
]
