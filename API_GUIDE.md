# Гайд по API webordo.kg — v1

**Base URL:** `https://webordo.kg/api/v1/`  
**Swagger UI:** `https://webordo.kg/api/docs/`  
**Формат:** JSON, snake_case, деньги строками (`"250.00"`), переводы `_ru / _ky / _en`

---

## Содержание

1. [Главный экран — категории](#1-главный-экран--категории)
2. [Список заведений категории](#2-список-заведений-категории)
3. [Детали заведения и его филиалы](#3-детали-заведения-и-его-филиалы)
4. [Меню / каталог филиала](#4-меню--каталог-филиала)
5. [Конструктор «Собери сам»](#5-конструктор-собери-сам)
6. [Поиск](#6-поиск)
7. [Заказ (доставка / самовывоз)](#7-заказ-доставка--самовывоз)
8. [Бронирование стола](#8-бронирование-стола)
9. [QR-стол (заказ с физического стола)](#9-qr-стол-заказ-с-физического-стола)
10. [Баннеры и промокоды](#10-баннеры-и-промокоды)
11. [Авторизация и профиль](#11-авторизация-и-профиль)
12. [История заказов](#12-история-заказов)
13. [Правила работы с API](#13-правила-работы-с-api)

---

## 1. Главный экран — категории

Приложение **не знает** список категорий заранее — оно получает их с сервера.
Добавили на сайте новую категорию → она сразу появилась на главном экране приложения, без релиза.

```
GET /api/v1/categories/
```

**Ответ:**
```json
[
  {
    "slug": "restaurants",
    "name_ru": "Еда",
    "name_ky": "Тамак-аш",
    "name_en": "Food",
    "subtitle_ru": "Меню, доставка, QR",
    "subtitle_ky": "",
    "subtitle_en": "",
    "icon": "🍽️",
    "sort_order": 1,
    "is_active": true,
    "supports_catalog": true,
    "supports_ordering": true,
    "supports_booking": false,
    "item_noun_ru": "Блюда",
    "item_noun_ky": "Тамактар",
    "item_noun_en": "Dishes"
  },
  {
    "slug": "hotels",
    "name_ru": "Отели",
    "name_ky": "Мейманканалар",
    "name_en": "Hotels",
    "subtitle_ru": "Бронирование номеров",
    "icon": "🏨",
    "sort_order": 2,
    "is_active": true,
    "supports_catalog": true,
    "supports_ordering": false,
    "supports_booking": true,
    "item_noun_ru": "Номера",
    "item_noun_ky": "",
    "item_noun_en": "Rooms"
  }
]
```

### Как использовать флаги поведения

| Флаг | Что показывать |
|---|---|
| `supports_catalog: true` | Кнопку «Меню» / «Каталог» → открывает `/branches/{id}/menu/` |
| `supports_ordering: true` | Корзину и оформление заказа |
| `supports_booking: true` | Кнопку «Забронировать» → открывает форму брони |
| `item_noun_ru` | Заголовок раздела с позициями («Блюда», «Номера», «Услуги») |

> Если категория пришла с незнакомым `slug` — показываем её как обычно по флагам.
> Приложение **не должно** хардкодить список категорий.

---

## 2. Список заведений категории

```
GET /api/v1/categories/{slug}/places/
```

**Пример:** `GET /api/v1/categories/restaurants/places/`

**Ответ:**
```json
[
  {
    "id": 12,
    "slug": "sonwich",
    "name_ru": "SONWICH",
    "name_ky": "",
    "name_en": "SONWICH",
    "logo_url": "https://webordo.kg/media/restaurants/logos/sonwich.png",
    "cover_url": "https://webordo.kg/media/restaurants/covers/sonwich_cover.jpg",
    "rating": "8.7",
    "branches_count": 3,
    "is_open_now": true
  }
]
```

> `cover_url` — если у заведения нет своей обложки, сервер автоматически берёт обложку первого активного филиала.
> `rating` — `null` если оценок ещё нет.

---

## 3. Детали заведения и его филиалы

### Детали заведения

```
GET /api/v1/categories/{slug}/places/{place_slug}/
```

**Пример:** `GET /api/v1/categories/restaurants/places/sonwich/`

**Ответ** — все поля из списка + дополнительно:
```json
{
  "id": 12,
  "slug": "sonwich",
  "name_ru": "SONWICH",
  "name_ky": "",
  "name_en": "SONWICH",
  "logo_url": "...",
  "cover_url": "...",
  "about_ru": "Сеть сэндвич-кафе",
  "phone": "+996700000000",
  "whatsapp": "+996700000000",
  "instagram": "https://instagram.com/sonwich",
  "telegram": "@sonwich",
  "map_url": "https://2gis.kg/...",
  "rating": "8.7",
  "branches_count": 3,
  "is_open_now": true,
  "place_category_slug": "restaurants"
}
```

### Филиалы заведения

```
GET /api/v1/categories/{slug}/places/{place_slug}/branches/
```

**Ответ:**
```json
[
  {
    "id": 37,
    "restaurant": "SONWICH",
    "name_ru": "SONWICH Баткенская",
    "name_ky": "",
    "name_en": "",
    "address": "ул. Баткенская 1/1",
    "phone": "+996700000001",
    "map_url": "https://2gis.kg/...",
    "cover_url": "...",
    "promo_photo_url": null,
    "lat": "42.870000",
    "lon": "74.590000",
    "is_open_now": true,
    "delivery_enabled": true,
    "min_order_amount": "500.00",
    "delivery_fee": "100.00",
    "free_delivery_from": "2000.00",
    "pay_cash_enabled": true,
    "pay_online_enabled": false,
    "is_open_24h": false,
    "open_time": "09:00:00",
    "close_time": "23:00:00"
  }
]
```

### Старые пути (совместимость)

Для уже выпущенных версий приложения старые пути продолжают работать:

```
GET /api/v1/restaurants/                         → список всех ресторанов
GET /api/v1/restaurants/{slug}/                  → детали ресторана
GET /api/v1/restaurants/{slug}/branches/         → филиалы ресторана
GET /api/v1/branches/{id}/                       → детали одного филиала
```

---

## 4. Меню / каталог филиала

```
GET /api/v1/branches/{id}/menu/
```

**Пример:** `GET /api/v1/branches/37/menu/`

**Ответ:**
```json
{
  "branch_id": 37,
  "branch_name": "SONWICH Баткенская",
  "categories": [
    {
      "category_id": 5,
      "category_name_ru": "Сэндвичи",
      "category_name_ky": "",
      "category_name_en": "Sandwiches",
      "items": [
        {
          "id": 501,
          "item_id": 88,
          "name_ru": "Классический",
          "name_ky": "",
          "name_en": "Classic",
          "description": "Курица, сыр, салат",
          "photo_url": "https://webordo.kg/media/items/photos/classic.jpg",
          "price": "250.00",
          "is_available": true,
          "rating": "9.2",
          "orders_count": 1847
        }
      ]
    }
  ]
}
```

> `rating` и `orders_count` — **новые поля** (добавлены в этом обновлении).
> `orders_count` используется для значка 🔥 «популярное».
> `id` — ID позиции в данном филиале (`branch_item_id`), используется при создании заказа.
> `item_id` — глобальный ID блюда (для ссылок, аналитики).

---

## 5. Конструктор «Собери сам»

```
GET /api/v1/branches/{id}/constructors/
```

**Ответ:**
```json
[
  {
    "id": 3,
    "name": "Собери свой бургер",
    "description": "",
    "photo_url": null,
    "base_price": "0.00",
    "is_active": true,
    "sort_order": 0,
    "groups": [
      {
        "id": 11,
        "name": "Булочка",
        "min_select": 1,
        "max_select": 1,
        "sort_order": 0,
        "ingredients": [
          {
            "id": 45,
            "name": "Классическая булочка",
            "description": "",
            "price": "0.00",
            "photo_url": null,
            "is_active": true,
            "sort_order": 0
          },
          {
            "id": 46,
            "name": "Булочка с кунжутом",
            "description": "",
            "price": "30.00",
            "photo_url": null,
            "is_active": true,
            "sort_order": 1
          }
        ]
      }
    ]
  }
]
```

### Как отправить заказ с конструктором

При создании заказа (доставка/самовывоз) конструктор передаётся внутри `items` через отдельный тип. Пример — см. раздел 7.

---

## 6. Поиск

```
GET /api/v1/search/?q={запрос}
GET /api/v1/search/?q={запрос}&category={slug}   // фильтр по категории
```

**Примеры:**
```
GET /api/v1/search/?q=плов
GET /api/v1/search/?q=бургер&category=restaurants
```

**Ответ:**
```json
{
  "places": [
    {
      "id": 12,
      "slug": "sonwich",
      "name_ru": "SONWICH",
      "name_ky": "",
      "name_en": "SONWICH",
      "logo_url": "...",
      "cover_url": "...",
      "rating": "8.7",
      "branches_count": 3,
      "is_open_now": true,
      "place_category_slug": "restaurants"
    }
  ],
  "items": [
    {
      "id": 501,
      "item_id": 88,
      "name_ru": "Классический бургер",
      "name_ky": "",
      "name_en": "Classic Burger",
      "description": "Говяжья котлета, сыр, салат",
      "photo_url": "...",
      "price": "350.00",
      "is_available": true,
      "rating": "9.1",
      "orders_count": 523,
      "branch_id": 37,
      "branch_name_ru": "SONWICH Баткенская",
      "branch_name_ky": "",
      "branch_name_en": "",
      "place_category_slug": "restaurants"
    }
  ]
}
```

> Лимит: 50 заведений + 50 позиций.  
> Если `q` пустой — вернётся `400 {"detail": "Параметр q обязателен."}`.  
> `place_category_slug` в результатах — чтобы приложение знало, в какой раздел вести при нажатии.

---

## 7. Заказ (доставка / самовывоз)

```
POST /api/v1/branches/{id}/order/
```

**Тело запроса:**
```json
{
  "type": "delivery",
  "items": [
    {"branch_item_id": 501, "qty": 2},
    {"branch_item_id": 502, "qty": 1}
  ],
  "customer_name": "Айгуль",
  "customer_phone": "+996700123456",
  "delivery_address": "ул. Токтогула 123, кв. 45",
  "payment_method": "cash",
  "comment": "Без лука",
  "promo_code": "SUMMER10"
}
```

| Поле | Обязательно | Значения |
|---|---|---|
| `type` | ✓ | `delivery` или `pickup` |
| `items` | ✓ | массив `{branch_item_id, qty}` |
| `customer_name` | ✓ | — |
| `customer_phone` | ✓ | — |
| `delivery_address` | при `type=delivery` | — |
| `payment_method` | нет (default: `cash`) | `cash` или `online` |
| `comment` | нет | — |
| `promo_code` | нет | — |

**Ответ `201`:**
```json
{
  "order_id": 112,
  "status": "new",
  "type": "delivery",
  "subtotal": "1200.00",
  "delivery_fee": "100.00",
  "discount": "120.00",
  "total": "1180.00",
  "promo_applied": true,
  "promo_message": "Скидка 10%"
}
```

### Проверить промокод (без создания заказа)

```
POST /api/v1/branches/{id}/promo/check/

{
  "code": "SUMMER10",
  "cart_total": "1200.00"
}
```

**Ответ:**
```json
{
  "valid": true,
  "discount_type": "percent",
  "discount_value": "10.00",
  "discount_amount": "120.00",
  "message": "Скидка 10%"
}
```

---

## 8. Бронирование стола

> Доступно для заведений с `supports_booking: true` в категории.

### Получить залы и столы

```
GET /api/v1/branches/{id}/floors/
```

**Ответ:**
```json
{
  "branch_id": 5,
  "branch_name": "Центральный",
  "floors": [
    {
      "id": 1,
      "name_ru": "Основной зал",
      "name_ky": "",
      "name_en": "",
      "sort_order": 0,
      "places": [
        {
          "id": 10,
          "title": "Стол 1",
          "type": "table",
          "seats": 4,
          "is_active": true,
          "is_busy": false,
          "photo_url": null,
          "x": 100,
          "y": 200
        }
      ]
    }
  ]
}
```

### Свободные места

```
GET /api/v1/branches/{id}/places/free/
```

### Создать бронь

```
POST /api/v1/branches/{id}/book/
Content-Type: application/json

{
  "place_id": 10,
  "customer_name": "Бакыт",
  "customer_phone": "+996555000000",
  "guests_count": 2,
  "comment": "День рождения"
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|:---:|---------|
| `place_id` | int | ✅ | ID места (стол/кабинка) из `/floors/` |
| `customer_name` | string | ✅ | Имя гостя |
| `customer_phone` | string | ✅ | Телефон гостя |
| `guests_count` | int ≥ 1 | — | Количество гостей (по умолчанию 2) |
| `comment` | string | — | Комментарий |

**Ответ `201`:**
```json
{
  "booking_id": 55,
  "status": "active",
  "status_label": "Активна",
  "place_id": 10,
  "place_title": "Стол 1",
  "guests_count": 2,
  "customer_name": "Бакыт",
  "customer_phone": "+996555000000",
  "comment": "День рождения",
  "started_at": "2026-07-12T19:00:00Z"
}
```

**Статусы брони:**

| Значение | Значение |
|----------|---------|
| `active` | Активна |
| `arrived` | Гость пришёл |
| `closed` | Закрыта |
| `canceled` | Отменена |

### Статус брони

```
GET /api/v1/bookings/{booking_id}/
```

**Ответ:** такой же объект `BookingResponse` как при создании.

---

## 9. QR-стол (заказ с физического стола)

Гость сканирует QR-наклейку на столике → открывается меню → делает заказ.

### Получить меню стола

```
GET /api/v1/qr/{token}/menu/
```

**Ответ:** такой же формат как `/branches/{id}/menu/`, плюс `table_id` и `table_number`.

### Создать заказ со стола

```
POST /api/v1/qr/{token}/order/

{
  "items": [
    {"branch_item_id": 501, "qty": 2},
    {"branch_item_id": 503, "qty": 1}
  ],
  "customer_name": "Азамат",
  "comment": "Без лука"
}
```

**Ответ `201`:**
```json
{
  "order_id": 105,
  "total": "850.00",
  "status": "new",
  "table": 3,
  "branch_id": 37
}
```

### Статус заказа (polling)

Приложение опрашивает раз в 5–10 секунд чтобы показать статус гостю.

```
GET /api/v1/orders/{order_id}/status/
```

**Ответ:**
```json
{
  "order_id": 105,
  "status": "cooking",
  "status_label": "Готовится",
  "total": "850.00",
  "items": [
    {"name": "Классический", "qty": 2, "price": "250.00", "total": "500.00"},
    {"name": "Кола 0.5л",    "qty": 1, "price": "120.00", "total": "120.00"}
  ]
}
```

**Статусы заказа:**

| `status` | `status_label` | Значение |
|---|---|---|
| `new` | Принят | Заказ создан |
| `accepted` | Подтверждён | Принят персоналом |
| `cooking` | Готовится | На кухне |
| `ready` | Готов | Можно забирать/несут |
| `closed` | Закрыт | Завершён |
| `cancelled` | Отменён | Отменён |

---

## 10. Баннеры и промокоды

### Баннеры главного экрана

```
GET /api/v1/banners/
```

**Ответ:**
```json
[
  {
    "id": 1,
    "title": "Летняя акция",
    "image_mobile_url": "https://webordo.kg/media/banners/mobile/summer.jpg",
    "image_tablet_url": "https://webordo.kg/media/banners/tablet/summer.jpg",
    "image_wide_url":   "https://webordo.kg/media/banners/wide/summer.jpg",
    "link_url": "https://webordo.kg/...",
    "sort_order": 1
  }
]
```

> Используйте `image_mobile_url` для телефонов, `image_wide_url` для планшетов.  
> При клике на баннер отправьте `POST /api/v1/banners/{id}/click/` (без тела).

### Промокоды филиала

```
GET /api/v1/branches/{id}/promos/
```

---

## 11. Авторизация и профиль

### Регистрация

```
POST /api/auth/register/

{
  "phone": "+996700123456",
  "password": "mypassword123",
  "name": "Айгуль"
}
```

### Вход

```
POST /api/auth/login/

{
  "phone": "+996700123456",
  "password": "mypassword123"
}
```

**Ответ:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

### Обновление токена

```
POST /api/auth/refresh/

{"refresh": "eyJ..."}
```

### Профиль

```
GET  /api/auth/me/                        // получить профиль
PATCH /api/auth/me/  {"name": "Новое имя"} // обновить
```

### Передача токена в запросах

Все запросы, требующие авторизации (история заказов), должны содержать заголовок:

```
Authorization: Bearer eyJ...
```

---

## 12. История заказов

> Требует авторизации (`Authorization: Bearer ...`).

```
GET /api/v1/orders/history/
GET /api/v1/orders/{order_id}/
```

**Пример ответа:**
```json
{
  "count": 3,
  "results": [
    {
      "id": 105,
      "type": "delivery",
      "type_label": "Доставка",
      "status": "closed",
      "status_label": "Закрыт",
      "branch_id": 11,
      "branch_name": "Центральный",
      "restaurant_name": "Sonwich",
      "subtotal": "850.00",
      "delivery_fee": "100.00",
      "total": "950.00",
      "payment_method": "cash",
      "delivery_address": "ул. Ленина 12",
      "comment": "",
      "created_at": "2026-07-12T15:30:00Z",
      "items": [
        {
          "type": "dish",
          "item_id": 88,
          "name": "Классический бургер",
          "qty": 2,
          "price": "350.00",
          "line_total": "700.00",
          "selections": null
        },
        {
          "type": "constructor",
          "item_id": 3,
          "name": "Собери сам — Бургер",
          "qty": 1,
          "price": "150.00",
          "line_total": "150.00",
          "selections": [
            {
              "gname": "Соус",
              "ings": [{"name": "BBQ", "extra_price": 0}]
            }
          ]
        }
      ]
    }
  ]
}
```

**Поле `type` у каждой позиции:**

| Значение | Описание |
|----------|---------|
| `dish` | Обычное блюдо из меню; `selections: null` |
| `constructor` | Позиция «Собери сам»; `selections` — массив выбранных групп и ингредиентов |

---

## 13. Правила работы с API

### Обратная совместимость

- Поля **только добавляются**, никогда не удаляются и не переименовываются.
- Новое поле в ответе — старая версия приложения его игнорирует, это нормально.
- Ломающие изменения выйдут только в `/api/v2/`, старые пути живут вечно.

### Фолбэк переводов

Если `name_ky` или `name_en` пустая строка — показывать `name_ru`.  
Поле никогда не будет **отсутствовать** в ответе (может быть пустой строкой `""`).

### Скрытие без удаления

Категории, заведения, позиции **не удаляются** из API — они скрываются через `is_active: false`.  
Если получили `is_active: false` — убираем из UI, не делаем 404.

### Формат ошибок

```json
{"detail": "Сообщение об ошибке"}          // одна ошибка
{"field_name": ["Текст ошибки поля"]}       // ошибки валидации
```

### Коды ответов

| Код | Значение |
|---|---|
| `200` | OK |
| `201` | Создано (заказ, бронь) |
| `400` | Ошибка валидации |
| `401` | Не авторизован |
| `403` | Нет доступа |
| `404` | Не найдено |

---

## Быстрый старт — типичный сценарий

```
1. GET /api/v1/categories/
   → строим главный экран из категорий

2. GET /api/v1/categories/restaurants/places/
   → список заведений категории «Еда»

3. GET /api/v1/categories/restaurants/places/sonwich/branches/
   → филиалы конкретного заведения

4. GET /api/v1/branches/37/menu/
   → меню выбранного филиала (rating + orders_count уже в ответе)

5. POST /api/v1/branches/37/order/
   → создаём заказ

6. GET /api/v1/orders/105/status/
   → следим за статусом (polling каждые 5-10 сек)
```

---

*Вопросы и swagger-документация: `https://webordo.kg/api/docs/`*
