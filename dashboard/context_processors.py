_ALL_TRUE = {
    "has_restaurants": True,
    "has_hotels": True,
    "has_shops": True,
    "has_karaoke": True,
    "has_barbershop": True,
    "has_simracing": True,
    "has_printshop": True,
    "has_legal": True,
    "has_agency": True,
    "has_eco": True,
}

_ALL_FALSE = {k: False for k in _ALL_TRUE}

_TTL = 300


def _compute_flags(user):
    """Реальные флаги по membership пользователя — какие категории бизнеса у него есть."""
    result = {}

    try:
        from core.models import Membership
        result["has_restaurants"] = Membership.objects.filter(user=user).exists()
    except Exception:
        result["has_restaurants"] = False

    try:
        from hotels.models import HotelMembership
        result["has_hotels"] = HotelMembership.objects.filter(user=user).exists()
    except Exception:
        result["has_hotels"] = False

    try:
        from shops.models import StoreMembership
        result["has_shops"] = StoreMembership.objects.filter(user=user).exists()
    except Exception:
        result["has_shops"] = False

    try:
        from karaoke.models import KaraokeMembership
        result["has_karaoke"] = KaraokeMembership.objects.filter(user=user).exists()
    except Exception:
        result["has_karaoke"] = False

    try:
        from barbershop.models import BarbershopMembership
        result["has_barbershop"] = BarbershopMembership.objects.filter(user=user).exists()
    except Exception:
        result["has_barbershop"] = False

    try:
        from simracing.models import SimRacingMembership
        result["has_simracing"] = SimRacingMembership.objects.filter(user=user).exists()
    except Exception:
        result["has_simracing"] = False

    try:
        from printshop.models import PrintMembership
        result["has_printshop"] = PrintMembership.objects.filter(user=user).exists()
    except Exception:
        result["has_printshop"] = False

    try:
        from legal.models import LegalMembership
        result["has_legal"] = LegalMembership.objects.filter(user=user).exists()
    except Exception:
        result["has_legal"] = False

    try:
        from agency.models import AgencyMembership
        result["has_agency"] = AgencyMembership.objects.filter(user=user).exists()
    except Exception:
        result["has_agency"] = False

    try:
        from eco.models import EcoMembership
        result["has_eco"] = EcoMembership.objects.filter(user=user).exists()
    except Exception:
        result["has_eco"] = False

    return result


def user_nav_access(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return _ALL_FALSE

    user = request.user
    cache_key = f"nav_access:{user.pk}"

    # кэш — только ускорение; его недоступность не должна ломать сайдбар
    try:
        from django.core.cache import cache
        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            return cached
    except Exception:
        cache = None

    try:
        flags = _compute_flags(user)
    except Exception:
        # если совсем не смогли посчитать — оставляем сайдбар видимым
        return dict(_ALL_TRUE)

    # Пункт меню показываем, только если у пользователя есть такой бизнес.
    # Исключение — «чистый» администратор без собственных бизнесов: ему показываем всё.
    if (user.is_staff or user.is_superuser) and not any(flags.values()):
        flags = dict(_ALL_TRUE)

    try:
        if cache is not None:
            cache.set(cache_key, flags, _TTL)
    except Exception:
        pass
    return flags


def clear_nav_cache(user_id: int) -> None:
    try:
        from django.core.cache import cache
        cache.delete(f"nav_access:{user_id}")
    except Exception:
        pass
