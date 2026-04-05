from django.shortcuts import render, get_object_or_404
from .models import Market


def market_list(request):
    markets = Market.objects.filter(is_active=True)
    return render(request, "markets/market_list.html", {"markets": markets})


def market_detail(request, slug):
    market = get_object_or_404(Market, slug=slug, is_active=True)
    return render(request, "markets/market_detail.html", {"market": market})
