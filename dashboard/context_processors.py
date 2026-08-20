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


def user_nav_access(request):
    try:
        from django.core.cache import cache

        if not request.user.is_authenticated:
            return _ALL_FALSE

        user = request.user

        if user.is_staff or user.is_superuser:
            return _ALL_TRUE

        cache_key = f"nav_access:{user.pk}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

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

        cache.set(cache_key, result, _TTL)
        return result

    except Exception:
        # If anything crashes — return all True so sidebar stays visible
        return _ALL_TRUE


def clear_nav_cache(user_id: int) -> None:
    try:
        from django.core.cache import cache
        cache.delete(f"nav_access:{user_id}")
    except Exception:
        pass
