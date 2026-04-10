import hashlib
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


# Порядок важен: более специфичные пути первее
_SECTION_PREFIXES = [
    ("/markets",    "markets"),
    ("/shops",      "shops"),
    ("/hotels",     "hotels"),
    ("/pharmacy",   "pharmacy"),
    ("/legal",      "legal"),
    ("/eco",        "eco"),
    ("/t/",         "restaurant"),   # меню за столиком
    # публичные страницы ресторанов вида /ru/<slug>/
]

_SKIP_PREFIXES = (
    "/cabinet/",
    "/admin/",
    "/static/",
    "/media/",
    "/i18n/",
    "/favicon",
)


def _detect_section(path: str) -> str | None:
    # убираем языковой префикс /ru/, /ky/, /en/
    stripped = path
    for lang in ("/ru/", "/ky/", "/en/"):
        if path.startswith(lang):
            stripped = path[len(lang) - 1:]  # оставляем ведущий /
            break

    # пропускаем личный кабинет и админку после срезания языкового префикса
    if any(stripped.startswith(s) for s in _SKIP_PREFIXES):
        return None

    for prefix, section in _SECTION_PREFIXES:
        if stripped.startswith(prefix):
            return section

    # Главная страница
    if stripped in ("/", ""):
        return "home"

    # Публичный сайт ресторана — любой путь не попавший выше
    return "restaurant"


class PageViewMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Записываем только успешные GET-запросы к HTML-страницам
        if request.method != "GET":
            return response
        if response.status_code not in (200,):
            return response

        path = request.path
        if any(path.startswith(s) for s in _SKIP_PREFIXES):
            return response

        # Пропускаем AJAX / API
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return response
        content_type = getattr(response, "get", lambda k, d="": response.get(k, d))("Content-Type", "")
        if "json" in content_type or "xml" in content_type:
            return response

        section = _detect_section(path)
        if not section:
            return response

        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", "")
        )
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:32]
        session_key = (request.session.session_key or "")[:64]

        try:
            from core.models import PageView
            PageView.objects.create(
                section=section,
                path=path[:500],
                ip_hash=ip_hash,
                session_key=session_key,
                timestamp=timezone.now(),
            )
        except Exception:
            pass  # никогда не ломаем пользовательский запрос

        return response
