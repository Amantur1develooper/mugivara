# -*- coding: utf-8 -*-
"""Меню «Mangal Burger» на трёх языках.

Источник: сайт заведения mangalburger.kg — названия, цены, составы и фото.
Русские названия причёсаны: на сайте встречались «Чиккен», «ЗапеченЫЙ»,
«coyce» латиницей и лишние точки.
"""

RESTAURANT = {
    "slug": "mangal-burger",
    "ru": "Mangal Burger", "ky": "Mangal Burger", "en": "Mangal Burger",
    "about_ru": "Бургеры, шаурма, пицца, роллы и WOK с доставкой.",
    "external_url": "https://mangalburger.kg/",
}

# Контакты и адрес на сайте не опубликованы — заполните в кабинете.
BRANCHES = [
    {"ru": "Mangal Burger — основной", "ky": "Mangal Burger — негизги",
     "en": "Mangal Burger — Main", "address": ""},
]

CATEGORIES = [
    {
        "slug": "combo",
        "ru": "Комбо", "ky": "Комбо", "en": "Combos",
        "items": [
            {
                "ru": "Наггетсы «Аль-Бейк», 8 шт.",
                "ky": "«Аль-Бейк» наггетс, 8 даана", "en": "Al-Beik Nuggets, 8 pcs",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 399, "photo": "1835.webp",
            },
            {
                "ru": "Наггетсы «Аль-Бейк», 12 шт.",
                "ky": "«Аль-Бейк» наггетс, 12 даана", "en": "Al-Beik Nuggets, 12 pcs",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 479, "photo": "1836.webp",
            },
            {
                "ru": "Комбо «Студент» №1",
                "ky": "«Студент» комбосу №1", "en": "Student Combo No. 1",
                "d_ru": "Мангал Бургер, фри 90 г, напиток 0,3 л и чесночный соус.", "d_ky": "Мангал Бургер, фри 90 г, суусундук 0,3 л жана сарымсак соусу.", "d_en": "Mangal Burger, fries 90 g, drink 0.3 L and garlic sauce.",
                "price": 359, "photo": "1837.webp",
            },
            {
                "ru": "Комбо «Студент» №2",
                "ky": "«Студент» комбосу №2", "en": "Student Combo No. 2",
                "d_ru": "Чикен-бургер, фри 90 г, напиток 0,3 л и чесночный соус.", "d_ky": "Чикен бургер, фри 90 г, суусундук 0,3 л жана сарымсак соусу.", "d_en": "Chicken Burger, fries 90 g, drink 0.3 L and garlic sauce.",
                "price": 289, "photo": "1838.webp",
            },
            {
                "ru": "Комбо «Студент» №3",
                "ky": "«Студент» комбосу №3", "en": "Student Combo No. 3",
                "d_ru": "Шаурма, фри 90 г, напиток 0,3 л и чесночный соус.", "d_ky": "Шаурма, фри 90 г, суусундук 0,3 л жана сарымсак соусу.", "d_en": "Shawarma, fries 90 g, drink 0.3 L and garlic sauce.",
                "price": 369, "photo": "1839.webp",
            },
            {
                "ru": "Комбо «Студент» №4",
                "ky": "«Студент» комбосу №4", "en": "Student Combo No. 4",
                "d_ru": "Хот-дог, фри 90 г, напиток 0,3 л и чесночный соус.", "d_ky": "Хот-дог, фри 90 г, суусундук 0,3 л жана сарымсак соусу.", "d_en": "Hot dog, fries 90 g, drink 0.3 L and garlic sauce.",
                "price": 259, "photo": "1840.webp",
            },
            {
                "ru": "Комбо «Шаурма»",
                "ky": "«Шаурма» комбосу", "en": "Shawarma Combo",
                "d_ru": "Шаурма куриная или говяжья, фри 90 г, напиток и соус.", "d_ky": "Тоок же уй этинен шаурма, фри 90 г, суусундук жана соус.", "d_en": "Chicken or beef shawarma, fries 90 g, drink and sauce.",
                "price": 399, "photo": "1842.webp",
            },
            {
                "ru": "Комбо «Микс» на 3 персоны",
                "ky": "3 кишиге «Микс» комбосу", "en": "Mix Combo for 3",
                "d_ru": "Сырный ролл, крылышки 6 шт., пицца «Пепперони» 35 см.", "d_ky": "Сырдуу ролл, канаттар 6 даана, «Пепперони» пицца 35 см.", "d_en": "Cheese roll, wings 6 pcs, Pepperoni pizza 35 cm.",
                "price": 1149, "photo": "1843.webp",
            },
            {
                "ru": "Комбо для двоих",
                "ky": "Экөөгө комбо", "en": "Combo for Two",
                "d_ru": "Бургеры, куриные стрипсы, картофель фри и напиток.", "d_ky": "Бургерлер, тоок стрипстери, фри картошка жана суусундук.", "d_en": "Burgers, chicken strips, french fries and a drink.",
                "price": 799, "photo": "1844.webp",
            },
            {
                "ru": "Комбо для семьи",
                "ky": "Үй-бүлөлүк комбо", "en": "Family Combo",
                "d_ru": "Большая пицца, крылышки, наггетсы, роллы и закуски.", "d_ky": "Чоң пицца, канаттар, наггетс, роллдор жана жеңил тамактар.", "d_en": "Large pizza, wings, nuggets, rolls and snacks.",
                "price": 1819, "photo": "1845.webp",
            },
        ],
    },
    {
        "slug": "soups",
        "ru": "Супы", "ky": "Шорполор", "en": "Soups",
        "items": [
            {
                "ru": "Рамен с говядиной",
                "ky": "Уй эти менен рамен", "en": "Beef Ramen",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 359, "photo": "1748.webp",
            },
            {
                "ru": "Сырный рамен",
                "ky": "Сырдуу рамен", "en": "Cheese Ramen",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 399, "photo": "1749.webp",
            },
        ],
    },
    {
        "slug": "salads",
        "ru": "Салаты", "ky": "Салаттар", "en": "Salads",
        "items": [
            {
                "ru": "Салат греческий",
                "ky": "Грек салаты", "en": "Greek Salad",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 299, "photo": "1746.webp",
            },
            {
                "ru": "Салат «Цезарь» с курицей",
                "ky": "Тоок менен «Цезарь» салаты", "en": "Caesar Salad with Chicken",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 289, "photo": "1747.webp",
            },
        ],
    },
    {
        "slug": "burgers",
        "ru": "Бургеры", "ky": "Бургерлер", "en": "Burgers",
        "items": [
            {
                "ru": "Чизбургер",
                "ky": "Чизбургер", "en": "Cheeseburger",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 299, "photo": "1750.webp",
            },
            {
                "ru": "Мангал Бургер",
                "ky": "Мангал Бургер", "en": "Mangal Burger",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 279, "photo": "1751.webp",
            },
            {
                "ru": "Биг Бургер",
                "ky": "Биг Бургер", "en": "Big Burger",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 349, "photo": "1752.webp",
            },
            {
                "ru": "Двойной донер-бургер",
                "ky": "Кош донер бургер", "en": "Double Doner Burger",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 249, "photo": "1753.webp",
            },
            {
                "ru": "Донер-бургер",
                "ky": "Донер бургер", "en": "Doner Burger",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 199, "photo": "1754.webp",
            },
            {
                "ru": "Ассорти-бургер",
                "ky": "Ассорти бургер", "en": "Assorted Burger",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 239, "photo": "1755.webp",
            },
            {
                "ru": "Чикен-бургер",
                "ky": "Чикен бургер", "en": "Chicken Burger",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 209, "photo": "1756.webp",
            },
            {
                "ru": "Чикен-бургер острый",
                "ky": "Ачуу чикен бургер", "en": "Spicy Chicken Burger",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 219, "photo": "1757.webp",
            },
            {
                "ru": "Шеф-бургер",
                "ky": "Шеф бургер", "en": "Chef Burger",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 229, "photo": "1758.webp",
            },
            {
                "ru": "Чикен-донер",
                "ky": "Чикен донер", "en": "Chicken Doner",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 199, "photo": "1759.webp",
            },
        ],
    },
    {
        "slug": "shawarma",
        "ru": "Шаурма и хот-доги", "ky": "Шаурма жана хот-дог", "en": "Shawarma & Hot Dogs",
        "items": [
            {
                "ru": "Мега Шаурма",
                "ky": "Мега Шаурма", "en": "Mega Shawarma",
                "d_ru": "Куриное и говяжье мясо, чесночный соус, помидор, огурец, картофель пай.", "d_ky": "Тоок жана уй эти, сарымсак соусу, помидор, бадыраң, картошка пай.", "d_en": "Chicken and beef, garlic sauce, tomato, cucumber, potato pie.",
                "price": 369, "photo": "1846.webp",
            },
            {
                "ru": "Чикен-дог",
                "ky": "Чикен дог", "en": "Chicken Dog",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 189, "photo": "1760.webp",
            },
            {
                "ru": "Ассорти-дог",
                "ky": "Ассорти дог", "en": "Assorted Dog",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 209, "photo": "1761.webp",
            },
            {
                "ru": "Двойной хот-дог",
                "ky": "Эгиз хот-дог", "en": "Double Hot Dog",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 159, "photo": "1762.webp",
            },
            {
                "ru": "Хот-дог",
                "ky": "Хот-дог", "en": "Hot Dog",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 129, "photo": "1763.webp",
            },
            {
                "ru": "Мини-шаверма с сыром",
                "ky": "Сыр менен мини шаверма", "en": "Mini Shawarma with Cheese",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 239, "photo": "1764.webp",
            },
            {
                "ru": "Шаурма классическая, курица",
                "ky": "Классикалык шаурма, тоок эти", "en": "Classic Shawarma, Chicken",
                "d_ru": "Куриное мясо, помидор, огурец, чесночный соус и картофель пай.", "d_ky": "Тоок эти, помидор, бадыраң, сарымсак соусу жана картошка пай.", "d_en": "Chicken, tomato, cucumber, garlic sauce and potato pie.",
                "price": 269, "photo": "1765.webp",
            },
            {
                "ru": "Шаурма классическая, говядина",
                "ky": "Классикалык шаурма, уй эти", "en": "Classic Shawarma, Beef",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 279, "photo": "1766.webp",
            },
            {
                "ru": "Шаурма с сыром, курица",
                "ky": "Быштак менен шаурма, тоок эти", "en": "Shawarma with Cheese, Chicken",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 289, "photo": "1767.webp",
            },
            {
                "ru": "Шаурма с сыром, говядина",
                "ky": "Быштак менен шаурма, уй эти", "en": "Shawarma with Cheese, Beef",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 299, "photo": "1768.webp",
            },
            {
                "ru": "Шаурма ассорти, курица",
                "ky": "Ассорти шаурма, тоок эти", "en": "Assorted Shawarma, Chicken",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 299, "photo": "1769.webp",
            },
            {
                "ru": "Шаурма ассорти, говядина",
                "ky": "Ассорти шаурма, уй эти", "en": "Assorted Shawarma, Beef",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 319, "photo": "1770.webp",
            },
            {
                "ru": "Твистер",
                "ky": "Твистер", "en": "Twister",
                "d_ru": "Стрипсы, помидор, огурец, чесночный соус и картофель пай.", "d_ky": "Стрипс, помидор, бадыраң, сарымсак соусу жана картошка пай.", "d_en": "Chicken strips, tomato, cucumber, garlic sauce and potato pie.",
                "price": 229, "photo": "1771.webp",
            },
            {
                "ru": "Твистер с сыром",
                "ky": "Быштак менен твистер", "en": "Twister with Cheese",
                "d_ru": "Стрипсы, помидор, огурец, сыр, чесночный соус и картофель пай.", "d_ky": "Стрипс, помидор, бадыраң, сыр, сарымсак соусу жана картошка пай.", "d_en": "Chicken strips, tomato, cucumber, cheese, garlic sauce and potato pie.",
                "price": 249, "photo": "1772.webp",
            },
        ],
    },
    {
        "slug": "pizza",
        "ru": "Пицца и крылышки", "ky": "Пицца жана канаттар", "en": "Pizza & Wings",
        "items": [
            {
                "ru": "Пицца «4 сезона», 30 см",
                "ky": "«4 мезгил» пицца, 30 см", "en": "Four Seasons Pizza, 30 cm",
                "d_ru": "Вкусная горячая пицца.", "d_ky": "Даамдуу ысык пицца.", "d_en": "Tasty hot pizza.",
                "price": 489, "photo": "1847.webp",
            },
            {
                "ru": "Пицца «4 сезона», 35 см",
                "ky": "«4 мезгил» пицца, 35 см", "en": "Four Seasons Pizza, 35 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 589, "photo": "1848.webp",
            },
            {
                "ru": "Крылышки, 6 шт.",
                "ky": "Канаттар, 6 даана", "en": "Chicken Wings, 6 pcs",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 299, "photo": "1773.webp",
            },
            {
                "ru": "Крылышки, 12 шт.",
                "ky": "Канаттар, 12 даана", "en": "Chicken Wings, 12 pcs",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 579, "photo": "1774.webp",
            },
            {
                "ru": "Крылышки, 18 шт.",
                "ky": "Канаттар, 18 даана", "en": "Chicken Wings, 18 pcs",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 859, "photo": "1775.webp",
            },
            {
                "ru": "Крылышки, 26 шт.",
                "ky": "Канаттар, 26 даана", "en": "Chicken Wings, 26 pcs",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 1119, "photo": "1776.webp",
            },
            {
                "ru": "Наггетсы, 6 шт.",
                "ky": "Наггетс, 6 даана", "en": "Nuggets, 6 pcs",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 249, "photo": "1777.webp",
            },
            {
                "ru": "Наггетсы, 4 шт.",
                "ky": "Наггетс, 4 даана", "en": "Nuggets, 4 pcs",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 199, "photo": "1778.webp",
            },
            {
                "ru": "Стрипсы, 200 г",
                "ky": "Стрипс, 200 г", "en": "Chicken Strips, 200 g",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 199, "photo": "1779.webp",
            },
            {
                "ru": "Стрипсы, 300 г",
                "ky": "Стрипс, 300 г", "en": "Chicken Strips, 300 g",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 279, "photo": "1780.webp",
            },
            {
                "ru": "Стрипсы, 500 г",
                "ky": "Стрипс, 500 г", "en": "Chicken Strips, 500 g",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 439, "photo": "1781.webp",
            },
            {
                "ru": "Картофель по-деревенски, M",
                "ky": "Айылча картошка, M", "en": "Potato Wedges, M",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 129, "photo": "1782.webp",
            },
            {
                "ru": "Картофель по-деревенски, L",
                "ky": "Айылча картошка, L", "en": "Potato Wedges, L",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 269, "photo": "1783.webp",
            },
            {
                "ru": "Картофель по-деревенски, XL",
                "ky": "Айылча картошка, XL", "en": "Potato Wedges, XL",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 229, "photo": "1784.webp",
            },
            {
                "ru": "Картофель фри, M",
                "ky": "Фри картошка, M", "en": "French Fries, M",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 119, "photo": "1785.webp",
            },
            {
                "ru": "Картофель фри, L",
                "ky": "Фри картошка, L", "en": "French Fries, L",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 169, "photo": "1786.webp",
            },
            {
                "ru": "Картофель фри, XL",
                "ky": "Фри картошка, XL", "en": "French Fries, XL",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 229, "photo": "1787.webp",
            },
            {
                "ru": "Пицца «Греческая», 35 см",
                "ky": "«Грек» пицца, 35 см", "en": "Greek Pizza, 35 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 559, "photo": "1788.webp",
            },
            {
                "ru": "Пицца «Греческая», 30 см",
                "ky": "«Грек» пицца, 30 см", "en": "Greek Pizza, 30 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 489, "photo": "1789.webp",
            },
            {
                "ru": "Пицца «Мексиканская», 35 см",
                "ky": "«Мексика» пицца, 35 см", "en": "Mexican Pizza, 35 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 659, "photo": "1790.webp",
            },
            {
                "ru": "Пицца «Мексиканская», 30 см",
                "ky": "«Мексика» пицца, 30 см", "en": "Mexican Pizza, 30 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 559, "photo": "1791.webp",
            },
            {
                "ru": "Пицца «Азиатская», 35 см",
                "ky": "«Азия» пицца, 35 см", "en": "Asian Pizza, 35 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 639, "photo": "1792.webp",
            },
            {
                "ru": "Пицца «Азиатская», 30 см",
                "ky": "«Азия» пицца, 30 см", "en": "Asian Pizza, 30 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 499, "photo": "1793.webp",
            },
            {
                "ru": "Пицца «Маргарита», 35 см",
                "ky": "«Маргарита» пицца, 35 см", "en": "Margherita Pizza, 35 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 489, "photo": "1794.webp",
            },
            {
                "ru": "Пицца «Маргарита», 30 см",
                "ky": "«Маргарита» пицца, 30 см", "en": "Margherita Pizza, 30 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 429, "photo": "1795.webp",
            },
            {
                "ru": "Пицца «4 сыра», 35 см",
                "ky": "«4 сыр» пицца, 35 см", "en": "Four Cheese Pizza, 35 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 559, "photo": "1796.webp",
            },
            {
                "ru": "Пицца «4 сыра», 30 см",
                "ky": "«4 сыр» пицца, 30 см", "en": "Four Cheese Pizza, 30 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 459, "photo": "1797.webp",
            },
            {
                "ru": "Пицца «Пепперони», 35 см",
                "ky": "«Пепперони» пицца, 35 см", "en": "Pepperoni Pizza, 35 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 569, "photo": "1798.webp",
            },
            {
                "ru": "Пицца «Пепперони», 30 см",
                "ky": "«Пепперони» пицца, 30 см", "en": "Pepperoni Pizza, 30 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 469, "photo": "1799.webp",
            },
            {
                "ru": "Пицца «Мясная», 30 см",
                "ky": "«Эттүү» пицца, 30 см", "en": "Meat Pizza, 30 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 529, "photo": "1800.webp",
            },
            {
                "ru": "Пицца «Мясная», 35 см",
                "ky": "«Эттүү» пицца, 35 см", "en": "Meat Pizza, 35 cm",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 639, "photo": "1801.webp",
            },
        ],
    },
    {
        "slug": "wok",
        "ru": "Горячие блюда и лапша WOK", "ky": "Ысык тамактар жана WOK кесме", "en": "Hot Dishes & WOK Noodles",
        "items": [
            {
                "ru": "Гюдон",
                "ky": "Гюдон", "en": "Gyudon",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 359, "photo": "1802.webp",
            },
            {
                "ru": "Оякодон",
                "ky": "Оякодон", "en": "Oyakodon",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 309, "photo": "1803.webp",
            },
            {
                "ru": "Курица в соусе терияки",
                "ky": "Терияки соусундагы тоок", "en": "Chicken in Teriyaki Sauce",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 399, "photo": "1804.webp",
            },
            {
                "ru": "Чикен спайси",
                "ky": "Чикен спайси", "en": "Spicy Chicken",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 339, "photo": "1805.webp",
            },
            {
                "ru": "Удон с курицей",
                "ky": "Тоок менен удон", "en": "Udon with Chicken",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 309, "photo": "1806.webp",
            },
        ],
    },
    {
        "slug": "baked-rolls",
        "ru": "Запечённые роллы", "ky": "Бышырылган роллдор", "en": "Baked Rolls",
        "items": [
            {
                "ru": "Сырный ролл",
                "ky": "Сырдуу ролл", "en": "Cheese Roll",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 399, "photo": "1807.webp",
            },
            {
                "ru": "Запечённый с лососем",
                "ky": "Кызыл балык менен бышырылган", "en": "Baked with Salmon",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 359, "photo": "1808.webp",
            },
            {
                "ru": "Запечённый с креветкой",
                "ky": "Креветка менен бышырылган", "en": "Baked with Shrimp",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 389, "photo": "1809.webp",
            },
            {
                "ru": "Яки краб",
                "ky": "Яки краб", "en": "Yaki Crab",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 419, "photo": "1810.webp",
            },
            {
                "ru": "Гриль чикен",
                "ky": "Гриль чикен", "en": "Grilled Chicken Roll",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 369, "photo": "1811.webp",
            },
            {
                "ru": "Гриль угорь",
                "ky": "Гриль угорь", "en": "Grilled Eel Roll",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 439, "photo": "1812.webp",
            },
            {
                "ru": "Мини-лососик",
                "ky": "Мини кызыл балык", "en": "Mini Salmon Roll",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 289, "photo": "1818.webp",
            },
            {
                "ru": "Мини-курочка",
                "ky": "Мини тоок", "en": "Mini Chicken Roll",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 229, "photo": "1819.webp",
            },
            {
                "ru": "Мини-крабик",
                "ky": "Мини краб", "en": "Mini Crab Roll",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 199, "photo": "1820.webp",
            },
        ],
    },
    {
        "slug": "cold-rolls",
        "ru": "Холодные роллы", "ky": "Муздак роллдор", "en": "Cold Rolls",
        "items": [
            {
                "ru": "Филадельфия классика",
                "ky": "Классикалык Филадельфия", "en": "Philadelphia Classic",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 519, "photo": "1813.webp",
            },
            {
                "ru": "Калифорния в кунжуте",
                "ky": "Кунжуттагы Калифорния", "en": "California in Sesame",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 329, "photo": "1814.webp",
            },
            {
                "ru": "Филадельфия микс",
                "ky": "Филадельфия микс", "en": "Philadelphia Mix",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 449, "photo": "1815.webp",
            },
            {
                "ru": "Сяки маки",
                "ky": "Сяки маки", "en": "Shake Maki",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 209, "photo": "1816.webp",
            },
            {
                "ru": "Капа маки",
                "ky": "Капа маки", "en": "Kappa Maki",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 139, "photo": "1817.webp",
            },
        ],
    },
    {
        "slug": "tempura-rolls",
        "ru": "Темпурные роллы", "ky": "Темпура роллдор", "en": "Tempura Rolls",
        "items": [
            {
                "ru": "Чикен темпура",
                "ky": "Чикен темпура", "en": "Chicken Tempura",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 409, "photo": "1821.webp",
            },
            {
                "ru": "Дыхание дракона",
                "ky": "Ажыдаардын деми", "en": "Dragon's Breath",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 469, "photo": "1822.webp",
            },
            {
                "ru": "Канада темпура",
                "ky": "Канада темпура", "en": "Canada Tempura",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 449, "photo": "1823.webp",
            },
            {
                "ru": "Филадельфия темпура",
                "ky": "Филадельфия темпура", "en": "Philadelphia Tempura",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 429, "photo": "1824.webp",
            },
        ],
    },
    {
        "slug": "desserts",
        "ru": "Десерты", "ky": "Десерттер", "en": "Desserts",
        "items": [
            {
                "ru": "Ролл «Гавайи»",
                "ky": "«Гавайи» роллу", "en": "Hawaii Roll",
                "d_ru": "", "d_ky": "", "d_en": "",
                "price": 329, "photo": "1831.webp",
            },
        ],
    },
]
