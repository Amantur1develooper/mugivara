from typing import Optional
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from core.models import Restaurant, Branch, Banner
from catalog.models import (
    BranchCategory, BranchCategoryItem, BranchItem,
    DishConstructor, ConstructorGroup, ConstructorIngredient,
)


class RestaurantSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = [
            "id", "slug", "name_ru", "name_ky", "name_en",
            "logo_url", "about_ru", "phone", "whatsapp",
            "instagram", "telegram", "map_url", "rating",
        ]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_logo_url(self, obj):
        request = self.context.get("request")
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return None


class BranchSerializer(serializers.ModelSerializer):
    is_open_now  = serializers.SerializerMethodField()
    cover_url    = serializers.SerializerMethodField()
    restaurant   = serializers.StringRelatedField()

    class Meta:
        model = Branch
        fields = [
            "id", "restaurant", "name_ru", "name_ky", "name_en",
            "address", "phone", "map_url", "cover_url",
            "lat", "lon", "is_open_now",
            "delivery_enabled", "min_order_amount", "delivery_fee",
            "free_delivery_from",
            "pay_cash_enabled", "pay_online_enabled",
            "is_open_24h", "open_time", "close_time",
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_is_open_now(self, obj):
        return obj.is_open_now()

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_cover_url(self, obj):
        request = self.context.get("request")
        if obj.cover_photo and request:
            return request.build_absolute_uri(obj.cover_photo.url)
        return None


class MenuItemSerializer(serializers.ModelSerializer):
    item_id     = serializers.IntegerField(source="item.id")
    name_ru     = serializers.CharField(source="item.name_ru")
    name_ky     = serializers.CharField(source="item.name_ky")
    name_en     = serializers.CharField(source="item.name_en")
    description = serializers.CharField(source="item.description_ru")
    photo_url   = serializers.SerializerMethodField()

    class Meta:
        model = BranchItem
        fields = [
            "id", "item_id",
            "name_ru", "name_ky", "name_en",
            "description", "photo_url",
            "price", "is_available",
        ]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_photo_url(self, obj):
        request = self.context.get("request")
        if obj.item.photo and request:
            return request.build_absolute_uri(obj.item.photo.url)
        return None


class MenuCategorySerializer(serializers.Serializer):
    category_id   = serializers.IntegerField()
    category_name_ru = serializers.CharField()
    category_name_ky = serializers.CharField()
    category_name_en = serializers.CharField()
    items         = MenuItemSerializer(many=True)


class BranchMenuSerializer(serializers.Serializer):
    branch_id   = serializers.IntegerField()
    branch_name = serializers.CharField()
    categories  = MenuCategorySerializer(many=True)


# ── Конструктор (собери сам) ──────────────────────────────────────────────────

class ConstructorIngredientSerializer(serializers.ModelSerializer):
    name        = serializers.CharField(source="display_name")
    description = serializers.CharField(source="display_description")
    price       = serializers.DecimalField(
        source="display_price", max_digits=10, decimal_places=2
    )
    photo_url   = serializers.SerializerMethodField()

    class Meta:
        model = ConstructorIngredient
        fields = ["id", "name", "description", "price", "photo_url", "is_active", "sort_order"]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_photo_url(self, obj):
        request = self.context.get("request")
        url = obj.display_photo_url
        if url and not url.startswith("http") and request:
            return request.build_absolute_uri(url)
        return url


class ConstructorGroupSerializer(serializers.ModelSerializer):
    ingredients = ConstructorIngredientSerializer(many=True, source="ingredients.all")

    class Meta:
        model = ConstructorGroup
        fields = ["id", "name", "min_select", "max_select", "sort_order", "ingredients"]


class DishConstructorSerializer(serializers.ModelSerializer):
    photo_url = serializers.SerializerMethodField()
    groups    = ConstructorGroupSerializer(many=True, source="groups.all")

    class Meta:
        model = DishConstructor
        fields = [
            "id", "name", "description", "photo_url",
            "base_price", "is_active", "sort_order", "groups",
        ]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_photo_url(self, obj):
        request = self.context.get("request")
        if obj.photo and request:
            return request.build_absolute_uri(obj.photo.url)
        return None


# ── Баннеры ───────────────────────────────────────────────────────────────────

class BannerSerializer(serializers.ModelSerializer):
    image_mobile_url = serializers.SerializerMethodField()
    image_wide_url   = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = ["id", "title", "image_mobile_url", "image_wide_url", "link_url", "sort_order"]

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image_mobile_url(self, obj):
        request = self.context.get("request")
        if obj.image_mobile and request:
            return request.build_absolute_uri(obj.image_mobile.url)
        return None

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image_wide_url(self, obj):
        request = self.context.get("request")
        if obj.image_wide and request:
            return request.build_absolute_uri(obj.image_wide.url)
        return None
