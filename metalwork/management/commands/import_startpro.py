# -*- coding: utf-8 -*-
"""Заводит производство «Старт-Про» (Ош) с каталогом из печатного буклета.

Каталог, цены и характеристики взяты из PDF заказчика; фотографии вытащены
из того же файла и лежат рядом в _startpro/. Команда идемпотентна: ищет по
названию, повторный запуск ничего не задваивает. --overwrite перезаписывает
тексты и цены у уже заведённых изделий, --with-photos — ещё и фотографии.

    python manage.py import_startpro
"""
from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from metalwork.models import (
    MetalCategory, MetalCompany, MetalProduct, MetalProductPhoto,
)

PHOTOS = Path(__file__).resolve().parent / "_startpro"

COMPANY = {
    "name": "Старт-Про",
    "name_ky": "Старт-Про",
    "name_en": "Start-Pro",
    "slug": "start-pro",
    "tagline": "Металлические двери, щиты и металлоконструкции на заказ",
    "tagline_ky": "Темир эшиктер, щиттер жана металл конструкциялар — заказ боюнча",
    "tagline_en": "Steel doors, cabinets and metalwork made to order",
    "description": (
        "Производим противопожарные, технические и входные двери, пожарные, "
        "электрические и сантехнические щиты, корзины для кондиционеров.\n"
        "Размер, внешний вид и стоимость изделия согласовываются индивидуально "
        "с учётом проекта заказчика."
    ),
    "description_ky": (
        "Өрткө каршы, техникалык жана кире бериш эшиктерди, өрт, электр жана "
        "сантехникалык щиттерди, кондиционер себеттерин чыгарабыз.\n"
        "Буюмдун өлчөмү, сырткы көрүнүшү жана баасы заказчиктин долбооруна "
        "жараша өзүнчө макулдашылат."
    ),
    "description_en": (
        "We manufacture fire-rated, technical and entrance doors, fire hose, "
        "electrical and plumbing cabinets, and air-conditioner cages.\n"
        "Size, finish and final price are agreed individually for each project."
    ),
    "phone": "0508 03 00 04",
    "whatsapp": "0777 01 38 81",
    "email": "startpro.osh@gmail.com",
    "instagram": "startpro_kg",
    "city": "Ош",
    "address": "ул. Үсөналиева, 4а",
    "work_hours": "",
    "cover": "fire-cab-lineup",
}

# ── характеристики: (русский, кыргызский, английский) ───────────────────────
COLOR_GREY   = ("Цвет: Серый", "Түсү: Боз", "Colour: Grey")
STEEL12      = ("Металл: 1,2 мм", "Металл: 1,2 мм", "Steel: 1.2 mm")
H2050        = ("Высота полотна: 2050 мм", "Каалганын бийиктиги: 2050 мм", "Leaf height: 2050 mm")
W950         = ("Ширина полотна: 950 мм", "Каалганын туурасы: 950 мм", "Leaf width: 950 mm")
W860         = ("Ширина полотна: 860 мм", "Каалганын туурасы: 860 мм", "Leaf width: 860 mm")
FIN_MM       = ("Отделка полотна: металл-металл", "Каалганын каптамасы: металл-металл",
                "Leaf finish: steel–steel")
FIN_MDF      = ("Отделка полотна: металл-МДФ", "Каалганын каптамасы: металл-МДФ",
                "Leaf finish: steel–MDF")
FIN_MDF2     = ("Отделка полотна: МДФ", "Каалганын каптамасы: МДФ", "Leaf finish: MDF")
KIT_MDF      = ("Комплектация: полотно + коробка + фурнитура",
                "Топтому: каалга + кутусу + фурнитура",
                "Supplied as: leaf + frame + hardware")
MATERIAL     = ("Материал: металл", "Материалы: металл", "Material: steel")
WALL         = ("Размещение: крепёж на стену", "Орнотулушу: дубалга бекитилет",
                "Mounting: wall-mounted")
RECESSED     = ("Размещение: встраиваемый", "Орнотулушу: ичине орнотулат", "Mounting: recessed")
CAB_COLORS   = ("Цвета: серый, белый, чёрный, жёлтый", "Түстөрү: боз, ак, кара, сары",
                "Colours: grey, white, black, yellow")

def color(ru, ky, en):
    return (f"Цвет: {ru}", f"Түсү: {ky}", f"Colour: {en}")

def dims(v):
    return (f"Габариты (ВхШхД): {v}", f"Өлчөмдөрү (БхЕхУ): {v}", f"Dimensions (H×W×D): {v}")

def weight(kg):
    return (f"Вес: {kg} кг", f"Салмагы: {kg} кг", f"Weight: {kg} kg")

def windows(n):
    return (f"Окошек: {n}", f"Терезечелер: {n}", f"Windows: {n}")

DOUBLE_SPECS = [
    ("Размеры: 1200×2050 мм", "Өлчөмдөрү: 1200×2050 мм", "Size: 1200×2050 mm"),
    ("Толщина полотна: 90–120 мм", "Каалганын калыңдыгы: 90–120 мм", "Leaf thickness: 90–120 mm"),
    ("Толщина металла: 1,2 мм", "Металлдын калыңдыгы: 1,2 мм", "Steel thickness: 1.2 mm"),
    ("Отделка внутри: панель МДФ 10–12 мм", "Ичи: МДФ панель 10–12 мм",
     "Inside finish: MDF panel 10–12 mm"),
    ("Утеплитель: минеральная вата", "Жылуулагычы: минералдык макта", "Insulation: mineral wool"),
    ("Верхний замок: KALE", "Үстүнкү кулпу: KALE", "Top lock: KALE"),
    ("Основной замок: KALE", "Негизги кулпу: KALE", "Main lock: KALE"),
    ("Ручка: «Диана», Россия", "Туткасы: «Диана», Россия", "Handle: Diana, Russia"),
    ("Глазок: стандарт, 1 шт", "Көзөнөк: стандарт, 1 даана", "Peephole: standard, 1 pc"),
    ("Петли: 140 мм, 3 шт, Россия", "Илмектери: 140 мм, 3 даана, Россия",
     "Hinges: 140 mm, 3 pcs, Russia"),
    ("Уплотнитель двери: 1 шт", "Эшиктин тыгыздагычы: 1 даана", "Door seal: 1 pc"),
    ("Уплотнитель короба: 2 шт", "Кутунун тыгыздагычы: 2 даана", "Frame seal: 2 pcs"),
]

# ── каталог ─────────────────────────────────────────────────────────────────
# (название ru, ky, en), цена, описание (ru, ky, en), характеристики, фото
CATALOG = [
 {
  "category": ("Противопожарные двери", "Өрткө каршы эшиктер", "Fire-rated doors", "🔥"),
  "products": [
   {"name": ("Противопожарная дверь со смотровым окном",
             "Көзөнөгү бар өрткө каршы эшик", "Fire-rated door with vision panel"),
    "price": 32000,
    "desc": ("Однопольная дверь с остеклённым проёмом — ставят там, где нужно видеть,"
             " что за дверью: лестничные клетки, коридоры, технические помещения.",
             "Айнектүү көзөнөгү бар бир каалгалуу эшик — эшиктин артын көрүү керек"
             " болгон жерлерге коюлат: тепкич аянтчалары, коридорлор, техникалык бөлмөлөр.",
             "Single-leaf door with a glazed vision panel — for stairwells, corridors"
             " and plant rooms where you need to see through."),
    "specs": [COLOR_GREY, STEEL12, H2050, W950, FIN_MM],
    "photo": "fire-glazed"},
   {"name": ("Противопожарная дверь глухая", "Көзөнөксүз өрткө каршы эшик",
             "Fire-rated door, solid"),
    "price": 32000,
    "desc": ("Глухое полотно без остекления — базовое исполнение для"
             " технических и складских помещений.",
             "Айнексиз бүтөө каалга — техникалык жана кампа бөлмөлөрү үчүн негизги вариант.",
             "Solid leaf without glazing — the standard option for plant and storage rooms."),
    "specs": [COLOR_GREY, STEEL12, H2050, W950, FIN_MM],
    "photo": "fire-solid"},
   {"name": ("Противопожарная дверь с системой «антипаника»",
             "«Антипаника» тутуму менен өрткө каршы эшик",
             "Fire-rated door with panic bar"),
    "price": 37000,
    "desc": ("Двупольная дверь с горизонтальной ручкой-антипаникой: открывается"
             " нажатием корпусом, без поиска ручки. Для эвакуационных выходов.",
             "«Антипаника» туткасы бар кош каалгалуу эшик: туткасын издебей,"
             " денең менен түртүп ачылат. Эвакуация чыгуулары үчүн.",
             "Double-leaf door with a horizontal panic bar — opens under body weight,"
             " no handle to find. For emergency exits."),
    "specs": [
      ("Высота дверного блока: 2050 мм, нестандарт до 2400 мм",
       "Эшик блогунун бийиктиги: 2050 мм, стандарттан тышкары 2400 ммге чейин",
       "Door block height: 2050 mm, up to 2400 mm to order"),
      ("Ширина дверного блока: 680, 780, 880, 980, 1080 мм",
       "Эшик блогунун туурасы: 680, 780, 880, 980, 1080 мм",
       "Door block width: 680, 780, 880, 980, 1080 mm"),
      ("Толщина полотна: 60 мм", "Каалганын калыңдыгы: 60 мм", "Leaf thickness: 60 mm"),
      ("Плотность заполнения полотна: 130 кг/м³", "Толтургучтун тыгыздыгы: 130 кг/м³",
       "Core density: 130 kg/m³"),
      ("Безотказность: 500 000 циклов открывания/закрывания",
       "Иштөө ресурсу: 500 000 ачып-жабуу цикли",
       "Durability: 500,000 open/close cycles"),
      ("Звукоизоляция: 33 дБ", "Үн изоляциясы: 33 дБ", "Sound insulation: 33 dB"),
    ],
    "photo": "fire-antipanic-1", "gallery": ["fire-antipanic-2"]},
  ],
 },
 {
  "category": ("Технические двери", "Техникалык эшиктер", "Technical doors", "🚪"),
  "products": [
   {"name": ("Техническая дверь", "Техникалык эшик", "Technical door"),
    "price": 18000,
    "desc": ("Дверь для подсобных, электрощитовых и подвальных помещений."
             " Порошковая окраска в любой цвет по RAL.",
             "Жардамчы бөлмөлөр, электр щиттери жана подвалдар үчүн эшик."
             " RAL боюнча каалаган түскө боёлот.",
             "A door for utility rooms, switch rooms and basements."
             " Powder-coated in any RAL colour."),
    "specs": [STEEL12, H2050, FIN_MM,
              ("Цвет: по RAL", "Түсү: RAL боюнча", "Colour: any RAL")],
    "photo": "tech-green", "gallery": ["tech-white"]},
  ],
 },
 {
  "category": ("Входные двери: металл-МДФ", "Кире бериш эшиктер: металл-МДФ",
               "Entrance doors: steel–MDF", "🏠"),
  "products": [
   {"name": ("Входная дверь «Чёрный / белый»", "«Кара / ак» кире бериш эшиги",
             "Entrance door, Black / White"), "price": 22000,
    "desc": ("Снаружи металл, внутри светлая МДФ-панель с фрезеровкой в клетку.",
             "Сырты металл, ичи торчолуу фрезаланган ачык түстөгү МДФ панель.",
             "Steel outside, light MDF panel with a grid routing inside."),
    "specs": [color("чёрный / белый", "кара / ак", "black / white"), STEEL12, H2050, W860, FIN_MDF],
    "photo": "mdf-black-white"},
   {"name": ("Входная дверь «Серебро / бетон снежный»",
             "«Күмүш / кар бетону» кире бериш эшиги",
             "Entrance door, Silver / Snow Concrete"), "price": 22000,
    "desc": ("Серебристое антивандальное покрытие снаружи, светлый бетон внутри.",
             "Сыртында күмүш түстүү вандалга чыдамдуу каптама, ичинде ачык бетон.",
             "Anti-vandal silver coating outside, light concrete décor inside."),
    "specs": [color("серебро / бетон снежный", "күмүш / кар бетону", "silver / snow concrete"),
              STEEL12, H2050, W860, FIN_MDF],
    "photo": "mdf-silver-concrete"},
   {"name": ("Входная дверь «Софт шампань»", "«Софт шампан» кире бериш эшиги",
             "Entrance door, Soft Champagne"), "price": 22000,
    "desc": ("Медный антик снаружи, классическая филёнчатая панель внутри.",
             "Сыртында жез антик, ичинде классикалык филёнкалуу панель.",
             "Antique copper outside, classic panelled MDF inside."),
    "specs": [color("софт шампань", "софт шампан", "soft champagne"),
              STEEL12, H2050, W860, FIN_MDF],
    "photo": "mdf-soft-champagne"},
   {"name": ("Входная дверь «Антик серебро / белая лиственница»",
             "«Антик күмүш / ак карагай» кире бериш эшиги",
             "Entrance door, Antique Silver / White Larch"), "price": 22000,
    "desc": ("Тёмное антик-серебро снаружи, светлая лиственница с молдингами внутри.",
             "Сыртында күңүрт антик күмүш, ичинде молдингдүү ачык карагай.",
             "Dark antique silver outside, white larch with mouldings inside."),
    "specs": [color("антик серебро / белая лиственница", "антик күмүш / ак карагай",
                    "antique silver / white larch"), STEEL12, H2050, W860, FIN_MDF],
    "photo": "mdf-antique-silver"},
  ],
 },
 {
  "category": ("Входные двери: МДФ-МДФ", "Кире бериш эшиктер: МДФ-МДФ",
               "Entrance doors: MDF–MDF", "🚪"),
  "products": [
   {"name": ("Входная дверь «Бетон снежный»", "«Кар бетону» кире бериш эшиги",
             "Entrance door, Snow Concrete"), "price": 27000,
    "desc": ("МДФ с обеих сторон: графичный рисунок снаружи, спокойный бетон внутри.",
             "Эки жагы тең МДФ: сыртында графикалык сүрөт, ичинде жайбаракат бетон.",
             "MDF on both sides: a graphic pattern outside, plain concrete inside."),
    "specs": [color("бетон снежный", "кар бетону", "snow concrete"),
              STEEL12, H2050, W860, FIN_MDF2, KIT_MDF],
    "photo": "mm-concrete-snow"},
   {"name": ("Входная дверь «Графит сандал»", "«Графит сандал» кире бериш эшиги",
             "Entrance door, Graphite Sandal"), "price": 27000,
    "desc": ("Тёмный графит снаружи, классическая арочная филёнка внутри.",
             "Сыртында күңүрт графит, ичинде классикалык арка филёнкасы.",
             "Dark graphite outside, a classic arched panel inside."),
    "specs": [color("графит сандал", "графит сандал", "graphite sandal"),
              STEEL12, H2050, W860, FIN_MDF2, KIT_MDF],
    "photo": "mm-graphite-sandal"},
   {"name": ("Входная дверь «Графит / белый снег»", "«Графит / ак кар» кире бериш эшиги",
             "Entrance door, Graphite / Snow White"), "price": 27000,
    "desc": ("Рельефная панель с чёрной вставкой снаружи, белая с чёрной полосой внутри.",
             "Сыртында кара кыстырмасы бар рельефтүү панель, ичинде кара тилкелүү ак панель.",
             "Textured panel with a black inlay outside, white with a black stripe inside."),
    "specs": [color("графит / белый снег", "графит / ак кар", "graphite / snow white"),
              STEEL12, H2050, W860, FIN_MDF2, KIT_MDF],
    "photo": "mm-graphite-white"},
   {"name": ("Входная дверь «Чёрный / белый снег»", "«Кара / ак кар» кире бериш эшиги",
             "Entrance door, Black / Snow White"), "price": 27000,
    "desc": ("Вертикальная рейка: чёрная снаружи, белая внутри.",
             "Тик рейка: сырты кара, ичи ак.",
             "Vertical slats: black outside, white inside."),
    "specs": [color("чёрный / белый снег", "кара / ак кар", "black / snow white"),
              STEEL12, H2050, W860, FIN_MDF2, KIT_MDF],
    "photo": "mm-black-white"},
  ],
 },
 {
  "category": ("Входные двери: двухстворчатые", "Кире бериш эшиктер: эки каалгалуу",
               "Entrance doors: double-leaf", "🚪"),
  "products": [
   {"name": ("Дверь входная двухстворчатая металлическая",
             "Эки каалгалуу темир кире бериш эшиги",
             "Double-leaf steel entrance door"), "price": 30000,
    "desc": ("Широкий проём на две створки: для подъездов, магазинов и частных домов"
             " с широким входом.",
             "Эки каалгалуу кең кире бериш: подъезддер, дүкөндөр жана кең кире бериши"
             " бар үйлөр үчүн.",
             "A wide opening on two leaves — for building entrances, shops and houses"
             " with a wide doorway."),
    "specs": DOUBLE_SPECS,
    "photo": "double-steel"},
   {"name": ("Дверь входная двухстворчатая с МДФ-панелями",
             "МДФ панелдүү эки каалгалуу кире бериш эшиги",
             "Double-leaf entrance door with MDF panels"), "price": 40000,
    "desc": ("То же полотно, но с отделкой МДФ и снаружи, и внутри — классический"
             " рисунок с филёнками.",
             "Ошол эле каалга, бирок сырты да, ичи да МДФ менен капталган —"
             " филёнкалуу классикалык сүрөт.",
             "The same leaf, finished with MDF on both faces — a classic panelled look."),
    "specs": DOUBLE_SPECS[:3] + [
      ("Отделка снаружи: панель МДФ 10–12 мм", "Сырты: МДФ панель 10–12 мм",
       "Outside finish: MDF panel 10–12 mm")] + DOUBLE_SPECS[3:],
    "photo": "double-mdf"},
  ],
 },
 {
  "category": ("Пожарные щиты", "Өрт щиттери", "Fire hose cabinets", "🧯"),
  "products": [
   {"name": ("Пожарный щит 1, односекционный", "Өрт щити 1, бир секциялуу",
             "Fire hose cabinet 1, single-section"), "price": 6200,
    "price_note": ("без монтажа", "монтажсыз", "excluding installation"),
    "desc": ("Односекционный шкаф под рукав и огнетушитель, навесной.",
             "Жең жана өрт өчүргүч үчүн бир секциялуу илме шкаф.",
             "Single-section wall cabinet for a hose and an extinguisher."),
    "specs": [dims("66×23×66 см"), MATERIAL, WALL],
    "photo": "fire-cab-1"},
   {"name": ("Пожарный щит 2, двухсекционный", "Өрт щити 2, эки секциялуу",
             "Fire hose cabinet 2, two-section"), "price": 7200,
    "price_note": ("без монтажа", "монтажсыз", "excluding installation"),
    "desc": ("Две секции: отдельно рукав, отдельно огнетушитель — удобнее"
             " обслуживать и быстрее достать.",
             "Эки секция: жең өзүнчө, өрт өчүргүч өзүнчө — тейлөөгө ыңгайлуу,"
             " тезирээк алынат.",
             "Two sections — hose and extinguisher apart: easier to service,"
             " faster to reach."),
    "specs": [dims("66×23×84 см"), MATERIAL, WALL],
    "photo": "fire-cab-2"},
   {"name": ("Пожарный щит 3, встраиваемый", "Өрт щити 3, ичине орнотулуучу",
             "Fire hose cabinet 3, recessed"), "price": 6000,
    "price_note": ("без монтажа", "монтажсыз", "excluding installation"),
    "desc": ("Утапливается в стену заподлицо — не торчит в коридоре и"
             " не мешает проходу.",
             "Дубалга бирдей деңгээлде орнотулат — коридордо чыгып турбайт"
             " жана өтүүгө тоскоол болбойт.",
             "Sits flush in the wall — nothing protrudes into the corridor."),
    "specs": [dims("66×30×60 см"), MATERIAL, RECESSED],
    "photo": "fire-cab-3"},
  ],
 },
 {
  "category": ("Электрические щиты", "Электр щиттери", "Electrical cabinets", "⚡"),
  "products": [
   {"name": ("Электрический щит 1", "Электр щити 1", "Electrical cabinet 1"),
    "price": 5500,
    "desc": ("Этажный щит на четыре счётчика с отдельным отсеком под автоматы.",
             "Төрт эсептегичке арналган кабат щити, автоматтар үчүн өзүнчө бөлүмү бар.",
             "Floor distribution cabinet for four meters with a separate breaker bay."),
    "specs": [dims("90×15×90 см"), MATERIAL, CAB_COLORS, windows(4), weight(19)],
    "photo": "el-cab-1"},
   {"name": ("Электрический щит 2", "Электр щити 2", "Electrical cabinet 2"),
    "price": 6000,
    "desc": ("То же, но на пять счётчиков — для площадок с большим числом квартир.",
             "Ошол эле, бирок беш эсептегичке — батирлери көп аянтчалар үчүн.",
             "The same cabinet for five meters — for landings with more flats."),
    "specs": [dims("90×15×90 см"), MATERIAL, CAB_COLORS, windows(5), weight(19)],
    "photo": "el-cab-2"},
  ],
 },
 {
  "category": ("Сантехнические щиты", "Сантехникалык щиттер", "Plumbing cabinets", "🔧"),
  "products": [
   {"name": ("Наружный сантехнический щит с одной дверью",
             "Бир эшиктүү сырткы сантехникалык щит",
             "Surface-mounted plumbing cabinet, one door"), "price": 4300,
    "desc": ("Навесной шкаф под коллектор и запорную арматуру — ставится на стену,"
             " без штробления.",
             "Коллектор жана арматура үчүн илме шкаф — дубалга орнотулат, оюу талап кылынбайт.",
             "Wall-mounted cabinet for a manifold and valves — no chasing required."),
    "specs": [dims("90×15×80 см"), MATERIAL, CAB_COLORS, weight(11)],
    "photo": "plumb-outer"},
   {"name": ("Внутренний сантехнический щит с одной дверью",
             "Бир эшиктүү ички сантехникалык щит",
             "Recessed plumbing cabinet, one door"), "price": 6000,
    "desc": ("Утапливается в нишу — дверца остаётся заподлицо со стеной.",
             "Оюкка орнотулат — эшикчеси дубал менен бирдей деңгээлде калат.",
             "Recessed into a niche — the door stays flush with the wall."),
    "specs": [dims("83×15×105 см"), MATERIAL, CAB_COLORS, weight(11)],
    "photo": "plumb-inner"},
  ],
 },
 {
  "category": ("Корзины для кондиционера", "Кондиционер себеттери",
               "Air conditioner cages", "❄️"),
  "products": [
   {"name": ("Корзина для кондиционера с лазерной резкой и логотипом",
             "Лазер менен кесилген, логотиби бар кондиционер себети",
             "AC cage with laser-cut logo"), "price": None,
    "desc": ("Лазерная резка по вашему эскизу: логотип, орнамент или геометрия."
             " Закрывает наружный блок и не портит фасад.",
             "Сиздин эскизиңиз боюнча лазердик кесүү: логотип, оймо-чийме же геометрия."
             " Сырткы блокту жабат, фасадды бузбайт.",
             "Laser cut to your artwork — logo, ornament or geometry. Hides the outdoor"
             " unit without spoiling the façade."),
    "specs": [MATERIAL,
              ("Покрытие: порошковая окраска", "Каптамасы: порошок менен боёо",
               "Finish: powder coating"),
              ("Рисунок: по эскизу заказчика", "Сүрөтү: заказчиктин эскизи боюнча",
               "Pattern: to the customer's artwork")],
    "photo": "ac-logo", "gallery": ["ac-logo-variants"]},
   {"name": ("Корзина для кондиционера, перфорация",
             "Кондиционер себети, перфорация", "AC cage, perforated"),
    "price": None,
    "desc": ("Стандартные и нестандартные размеры под любой наружный блок."
             " Проектируем с учётом типа крепления и условий эксплуатации.",
             "Каалаган сырткы блокко стандарттуу жана стандарттан тышкары өлчөмдөр."
             " Бекитүү түрүн жана иштөө шарттарын эске алып долбоорлойбуз.",
             "Standard and custom sizes for any outdoor unit, designed around the"
             " mounting type and operating conditions."),
    "specs": [MATERIAL,
              ("Размер: под размер блока", "Өлчөмү: блоктун өлчөмү боюнча",
               "Size: to fit the unit"),
              ("Покрытие: порошковая окраска", "Каптамасы: порошок менен боёо",
               "Finish: powder coating")],
    "photo": "ac-perforated",
    "gallery": ["ac-mesh", "ac-tall", "ac-dark", "ac-geometric"]},
   {"name": ("Кронштейн для наружного блока", "Сырткы блок үчүн кронштейн",
             "Bracket for the outdoor unit"), "price": None,
    "desc": ("Усиленный кронштейн под наружный блок — отдельно или вместе с корзиной.",
             "Сырткы блок үчүн бекемделген кронштейн — өзүнчө же себет менен кошо.",
             "Reinforced bracket for the outdoor unit — on its own or with a cage."),
    "specs": [MATERIAL,
              ("Исполнение: оцинкованная сталь", "Аткарылышы: цинктелген болот",
               "Material: galvanised steel")],
    "photo": "ac-bracket"},
  ],
 },
]


def joined(rows, idx):
    return "\n".join(r[idx] for r in rows)


class Command(BaseCommand):
    help = "Заводит производство «Старт-Про» с каталогом из буклета"

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true",
                            help="обновить тексты и цены у уже заведённых изделий")
        parser.add_argument("--with-photos", action="store_true",
                            help="перезалить фотографии (по умолчанию только у новых)")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **o):
        self.overwrite = o["overwrite"]
        with transaction.atomic():
            company, created = MetalCompany.objects.get_or_create(
                slug=COMPANY["slug"],
                defaults={k: v for k, v in COMPANY.items() if k != "cover"},
            )
            self.stdout.write(
                ("Создано производство: " if created else "Производство уже есть: ")
                + f"#{company.id} {company.name}")
            if created or self.overwrite:
                for k, v in COMPANY.items():
                    if k != "cover":
                        setattr(company, k, v)
                company.save()
            if (created or o["with_photos"]) and not company.cover:
                self._set_photo(company, "cover", COMPANY["cover"])
                company.save()

            n_cat = n_new = n_upd = n_ph = 0
            for order, block in enumerate(CATALOG):
                ru, ky, en, icon = block["category"]
                cat, c_created = MetalCategory.objects.get_or_create(
                    company=company, name=ru,
                    defaults={"name_ky": ky, "name_en": en, "icon": icon, "sort_order": order},
                )
                if c_created:
                    n_cat += 1
                elif self.overwrite:
                    cat.name_ky, cat.name_en, cat.icon, cat.sort_order = ky, en, icon, order
                    cat.save()

                for pos, row in enumerate(block["products"]):
                    p_ru, p_ky, p_en = row["name"]
                    product, p_created = MetalProduct.objects.get_or_create(
                        company=company, name=p_ru, defaults={"category": cat},
                    )
                    if p_created:
                        n_new += 1
                    elif not self.overwrite:
                        self.stdout.write(f"  = {p_ru} (уже есть, пропускаю)")
                        continue
                    else:
                        n_upd += 1

                    note = row.get("price_note", ("", "", ""))
                    product.category      = cat
                    product.name_ky       = p_ky
                    product.name_en       = p_en
                    product.description, product.description_ky, product.description_en = row["desc"]
                    product.specs         = joined(row["specs"], 0)
                    product.specs_ky      = joined(row["specs"], 1)
                    product.specs_en      = joined(row["specs"], 2)
                    product.price         = Decimal(row["price"]) if row["price"] else None
                    product.price_from    = row["price"] is not None
                    product.price_note, product.price_note_ky, product.price_note_en = note
                    product.is_custom     = True
                    product.sort_order    = pos
                    if p_created or o["with_photos"]:
                        if self._set_photo(product, "photo", row["photo"]):
                            n_ph += 1
                    product.save()

                    if p_created or o["with_photos"]:
                        if o["with_photos"]:
                            product.photos.all().delete()
                        for i, key in enumerate(row.get("gallery", [])):
                            path = PHOTOS / f"{key}.webp"
                            if not path.exists():
                                self.stderr.write(f"    нет файла {path.name}")
                                continue
                            ph = MetalProductPhoto(product=product, sort_order=i)
                            with path.open("rb") as fh:
                                ph.photo.save(path.name, File(fh), save=False)
                            ph.save()
                            n_ph += 1
                    self.stdout.write(f"  {'+' if p_created else '~'} {p_ru}")

            if o["dry_run"]:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(f"Разделов создано: {n_cat}")
        self.stdout.write(f"Изделий создано:  {n_new}, обновлено: {n_upd}")
        self.stdout.write(f"Фотографий:       {n_ph}")
        if o["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: ничего не сохранено."))
        else:
            self.stdout.write(f"Каталог: /ru/metal/{company.slug}/")

    def _set_photo(self, obj, field, key):
        path = PHOTOS / f"{key}.webp"
        if not path.exists():
            self.stderr.write(f"    нет файла {path.name}")
            return False
        with path.open("rb") as fh:
            getattr(obj, field).save(path.name, File(fh), save=False)
        return True
