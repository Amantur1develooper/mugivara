from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiExample, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.models import Branch
from reservations.models import Floor, Place, Booking


# ── Схемы ─────────────────────────────────────────────────────────────────────

_PlaceSchema = inline_serializer("Place", fields={
    "id":        serializers.IntegerField(),
    "title":     serializers.CharField(),
    "type":      serializers.CharField(help_text="table | cabin"),
    "seats":     serializers.IntegerField(),
    "is_active": serializers.BooleanField(),
    "is_busy":   serializers.BooleanField(help_text="True — стол уже занят"),
    "photo_url": serializers.CharField(allow_null=True),
    "x":         serializers.IntegerField(help_text="Координата для плана зала"),
    "y":         serializers.IntegerField(help_text="Координата для плана зала"),
})

_FloorSchema = inline_serializer("Floor", fields={
    "id":        serializers.IntegerField(),
    "name_ru":   serializers.CharField(),
    "name_ky":   serializers.CharField(),
    "name_en":   serializers.CharField(),
    "sort_order": serializers.IntegerField(),
    "places":    serializers.ListField(child=_PlaceSchema),
})

_BookingCreateRequest = inline_serializer("BookingCreateRequest", fields={
    "place_id":       serializers.IntegerField(),
    "customer_name":  serializers.CharField(),
    "customer_phone": serializers.CharField(),
    "guests_count":   serializers.IntegerField(min_value=1, default=2),
    "comment":        serializers.CharField(required=False, allow_blank=True),
})

_BookingResponse = inline_serializer("BookingResponse", fields={
    "booking_id":     serializers.IntegerField(),
    "status":         serializers.CharField(),
    "status_label":   serializers.CharField(),
    "place_id":       serializers.IntegerField(),
    "place_title":    serializers.CharField(),
    "guests_count":   serializers.IntegerField(),
    "customer_name":  serializers.CharField(),
    "customer_phone": serializers.CharField(),
    "comment":        serializers.CharField(),
    "started_at":     serializers.DateTimeField(),
})

_STATUS_LABELS = {
    Booking.Status.ACTIVE:   "Активна",
    Booking.Status.ARRIVED:  "Гость пришёл",
    Booking.Status.CLOSED:   "Закрыта",
    Booking.Status.CANCELED: "Отменена",
}


def _serialize_booking(booking):
    return {
        "booking_id":     booking.id,
        "status":         booking.status,
        "status_label":   _STATUS_LABELS.get(booking.status, booking.status),
        "place_id":       booking.place_id,
        "place_title":    booking.place.title,
        "guests_count":   booking.guests_count,
        "customer_name":  booking.customer_name,
        "customer_phone": booking.customer_phone,
        "comment":        booking.comment or "",
        "started_at":     booking.started_at,
    }


# ── Views ─────────────────────────────────────────────────────────────────────

@extend_schema(
    summary="Этажи и столики филиала",
    description=(
        "Возвращает план зала: этажи со списком мест. "
        "Каждое место содержит `is_busy` — можно показать доступность в реальном времени."
    ),
    responses={
        200: inline_serializer("FloorsResponse", fields={
            "branch_id":   serializers.IntegerField(),
            "branch_name": serializers.CharField(),
            "floors":      serializers.ListField(child=_FloorSchema),
        }),
    },
    tags=["Бронирование"],
)
@api_view(["GET"])
def branch_floors(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)

    # Занятые места
    busy_place_ids = set(
        Booking.objects.filter(
            branch=branch,
            status__in=[Booking.Status.ACTIVE, Booking.Status.ARRIVED],
        ).values_list("place_id", flat=True)
    )

    floors_qs = (
        Floor.objects
        .prefetch_related("places")
        .filter(branch=branch, is_active=True)
        .order_by("sort_order", "id")
    )

    floors_data = []
    for floor in floors_qs:
        places = []
        for place in floor.places.filter(is_active=True).order_by("id"):
            photo_url = None
            if place.photo:
                req = request
                photo_url = req.build_absolute_uri(place.photo.url)
            places.append({
                "id":        place.id,
                "title":     place.title,
                "type":      place.type,
                "seats":     place.seats,
                "is_active": place.is_active,
                "is_busy":   place.id in busy_place_ids,
                "photo_url": photo_url,
                "x":         place.x,
                "y":         place.y,
            })
        floors_data.append({
            "id":         floor.id,
            "name_ru":    floor.name_ru,
            "name_ky":    floor.name_ky,
            "name_en":    floor.name_en,
            "sort_order": floor.sort_order,
            "places":     places,
        })

    return Response({
        "branch_id":   branch.id,
        "branch_name": branch.name_ru,
        "floors":      floors_data,
    })


@extend_schema(
    summary="Свободные места для бронирования",
    description=(
        "Возвращает только свободные места (is_busy=False) по всему филиалу. "
        "Используется для быстрого выбора стола без схемы зала."
    ),
    responses={200: inline_serializer("FreePlacesList", fields={
        "places": serializers.ListField(child=inline_serializer("FreePlaceItem", fields={
            "id": serializers.IntegerField(), "title": serializers.CharField(),
            "type": serializers.CharField(), "seats": serializers.IntegerField(),
            "is_busy": serializers.BooleanField(), "photo_url": serializers.CharField(allow_null=True),
            "x": serializers.IntegerField(), "y": serializers.IntegerField(),
        }))
    })},
    tags=["Бронирование"],
)
@api_view(["GET"])
def branch_free_places(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)

    busy_ids = set(
        Booking.objects.filter(
            branch=branch,
            status__in=[Booking.Status.ACTIVE, Booking.Status.ARRIVED],
        ).values_list("place_id", flat=True)
    )

    places = Place.objects.filter(
        floor__branch=branch, floor__is_active=True, is_active=True,
    ).exclude(id__in=busy_ids).order_by("floor__sort_order", "id")

    data = [
        {
            "id":        p.id,
            "title":     p.title,
            "type":      p.type,
            "seats":     p.seats,
            "is_active": p.is_active,
            "is_busy":   False,
            "photo_url": request.build_absolute_uri(p.photo.url) if p.photo else None,
            "x":         p.x,
            "y":         p.y,
        }
        for p in places
    ]
    return Response(data)


@extend_schema(
    summary="Забронировать стол",
    description=(
        "Создаёт бронь на конкретное место. "
        "Если место уже занято — возвращает `409 Conflict`. "
        "Используется защита от гонок (SELECT FOR UPDATE)."
    ),
    request=_BookingCreateRequest,
    responses={
        201: _BookingResponse,
        400: inline_serializer("BookingValidationError", fields={"detail": serializers.CharField()}),
        404: inline_serializer("BookingNotFound",        fields={"detail": serializers.CharField()}),
        409: inline_serializer("BookingConflict",        fields={"detail": serializers.CharField()}),
    },
    examples=[
        OpenApiExample(
            "Запрос",
            value={
                "place_id": 5, "customer_name": "Айбек",
                "customer_phone": "+996700111222",
                "guests_count": 3, "comment": "У окна",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Ответ",
            value={
                "booking_id": 42, "status": "active", "status_label": "Активна",
                "place_id": 5, "place_title": "Стол 5",
                "guests_count": 3, "customer_name": "Айбек",
                "customer_phone": "+996700111222",
                "comment": "У окна", "started_at": "2025-06-18T14:30:00+06:00",
            },
            response_only=True,
        ),
    ],
    tags=["Бронирование"],
)
@api_view(["POST"])
def booking_create(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)

    place_id      = request.data.get("place_id")
    customer_name = request.data.get("customer_name", "").strip()
    customer_phone = request.data.get("customer_phone", "").strip()
    guests_count  = request.data.get("guests_count", 2)
    comment       = request.data.get("comment", "").strip()

    if not place_id:
        return Response({"detail": "Поле place_id обязательно."}, status=400)
    if not customer_name or not customer_phone:
        return Response({"detail": "customer_name и customer_phone обязательны."}, status=400)

    try:
        guests_count = int(guests_count)
        if guests_count < 1:
            raise ValueError
    except (ValueError, TypeError):
        return Response({"detail": "guests_count должен быть целым числом >= 1."}, status=400)

    place = get_object_or_404(Place, id=place_id, floor__branch=branch, is_active=True)

    try:
        booking = Booking.create_active_booking(
            branch=branch,
            place=place,
            customer_name=customer_name,
            customer_phone=customer_phone,
            guests_count=guests_count,
            comment=comment,
        )
    except ValueError:
        return Response(
            {"detail": "Это место уже занято. Выберите другое."},
            status=status.HTTP_409_CONFLICT,
        )

    return Response(_serialize_booking(booking), status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Статус брони",
    description="Возвращает текущий статус бронирования по его ID.",
    responses={
        200: _BookingResponse,
        404: inline_serializer("BookingStatusNotFound", fields={"detail": serializers.CharField()}),
    },
    tags=["Бронирование"],
)
@api_view(["GET"])
def booking_status(request, booking_id: int):
    booking = get_object_or_404(
        Booking.objects.select_related("place"),
        id=booking_id,
    )
    return Response(_serialize_booking(booking))
