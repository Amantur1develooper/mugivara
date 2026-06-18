from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiExample, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import UserProfile

User = get_user_model()


# ── Схемы ─────────────────────────────────────────────────────────────────────

_RegisterRequest = inline_serializer("RegisterRequest", fields={
    "phone":      serializers.CharField(help_text="Номер телефона, напр. +996700123456"),
    "password":   serializers.CharField(help_text="Пароль (мин. 6 символов)"),
    "first_name": serializers.CharField(required=False, allow_blank=True),
    "last_name":  serializers.CharField(required=False, allow_blank=True),
})

_LoginRequest = inline_serializer("LoginRequest", fields={
    "phone":    serializers.CharField(),
    "password": serializers.CharField(),
})

_TokenResponse = inline_serializer("TokenResponse", fields={
    "access":  serializers.CharField(),
    "refresh": serializers.CharField(),
    "user": inline_serializer("TokenUser", fields={
        "id":         serializers.IntegerField(),
        "phone":      serializers.CharField(),
        "first_name": serializers.CharField(),
        "last_name":  serializers.CharField(),
    }),
})

_MeResponse = inline_serializer("MeResponse", fields={
    "id":         serializers.IntegerField(),
    "phone":      serializers.CharField(),
    "first_name": serializers.CharField(),
    "last_name":  serializers.CharField(),
    "email":      serializers.CharField(),
})

_MeUpdateRequest = inline_serializer("MeUpdateRequest", fields={
    "first_name": serializers.CharField(required=False),
    "last_name":  serializers.CharField(required=False),
    "email":      serializers.CharField(required=False),
})

_PasswordChangeRequest = inline_serializer("PasswordChangeRequest", fields={
    "old_password": serializers.CharField(),
    "new_password": serializers.CharField(help_text="Мин. 6 символов"),
})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)


def _user_data(user):
    phone = ""
    try:
        phone = user.profile.phone
    except UserProfile.DoesNotExist:
        pass
    return {
        "id":         user.id,
        "phone":      phone,
        "first_name": user.first_name,
        "last_name":  user.last_name,
        "email":      user.email,
    }


# ── Views ─────────────────────────────────────────────────────────────────────

@extend_schema(
    summary="Регистрация по номеру телефона",
    description=(
        "Создаёт нового пользователя. Телефон используется как логин. "
        "Возвращает JWT токены — пользователь сразу авторизован."
    ),
    request=_RegisterRequest,
    responses={
        201: _TokenResponse,
        400: inline_serializer("RegisterError", fields={"detail": serializers.CharField()}),
    },
    examples=[
        OpenApiExample(
            "Запрос",
            value={"phone": "+996700123456", "password": "mypass123",
                   "first_name": "Азамат", "last_name": "Бейшенов"},
            request_only=True,
        ),
    ],
    tags=["Auth"],
)
@api_view(["POST"])
def register_view(request):
    phone      = request.data.get("phone", "").strip()
    password   = request.data.get("password", "")
    first_name = request.data.get("first_name", "").strip()
    last_name  = request.data.get("last_name", "").strip()

    if not phone:
        return Response({"detail": "Поле phone обязательно."}, status=400)
    if len(password) < 6:
        return Response({"detail": "Пароль должен быть не менее 6 символов."}, status=400)
    if UserProfile.objects.filter(phone=phone).exists():
        return Response({"detail": "Пользователь с таким номером уже существует."}, status=400)

    with transaction.atomic():
        user = User.objects.create_user(
            username=phone,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        UserProfile.objects.create(user=user, phone=phone)

    access, refresh = _tokens_for(user)
    return Response(
        {"access": access, "refresh": refresh, "user": _user_data(user)},
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    summary="Вход по номеру телефона",
    description="Возвращает пару JWT токенов. access — 60 мин, refresh — 30 дней.",
    request=_LoginRequest,
    responses={
        200: _TokenResponse,
        401: inline_serializer("LoginError", fields={"detail": serializers.CharField()}),
    },
    examples=[
        OpenApiExample(
            "Запрос",
            value={"phone": "+996700123456", "password": "mypass123"},
            request_only=True,
        ),
    ],
    tags=["Auth"],
)
@api_view(["POST"])
def login_view(request):
    phone    = request.data.get("phone", "").strip()
    password = request.data.get("password", "")

    if not phone or not password:
        return Response({"detail": "phone и password обязательны."}, status=400)

    try:
        profile = UserProfile.objects.select_related("user").get(phone=phone)
        user = profile.user
    except UserProfile.DoesNotExist:
        return Response({"detail": "Неверный номер или пароль."}, status=401)

    if not user.check_password(password):
        return Response({"detail": "Неверный номер или пароль."}, status=401)

    if not user.is_active:
        return Response({"detail": "Аккаунт заблокирован."}, status=401)

    access, refresh = _tokens_for(user)
    return Response({"access": access, "refresh": refresh, "user": _user_data(user)})


@extend_schema(
    summary="Профиль текущего пользователя",
    description="GET — получить профиль. PATCH — обновить имя / email.",
    request=_MeUpdateRequest,
    responses={200: _MeResponse},
    tags=["Auth"],
)
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me_view(request):
    user = request.user

    if request.method == "PATCH":
        if "first_name" in request.data:
            user.first_name = request.data["first_name"].strip()
        if "last_name" in request.data:
            user.last_name = request.data["last_name"].strip()
        if "email" in request.data:
            user.email = request.data["email"].strip()
        user.save(update_fields=["first_name", "last_name", "email"])

    return Response(_user_data(user))


@extend_schema(
    summary="Смена пароля",
    description="Требует авторизации. Принимает старый пароль и новый.",
    request=_PasswordChangeRequest,
    responses={
        200: inline_serializer("PasswordChanged", fields={"detail": serializers.CharField()}),
        400: inline_serializer("PasswordError",   fields={"detail": serializers.CharField()}),
    },
    tags=["Auth"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    old_password = request.data.get("old_password", "")
    new_password = request.data.get("new_password", "")

    if not request.user.check_password(old_password):
        return Response({"detail": "Неверный текущий пароль."}, status=400)
    if len(new_password) < 6:
        return Response({"detail": "Новый пароль должен быть не менее 6 символов."}, status=400)

    request.user.set_password(new_password)
    request.user.save(update_fields=["password"])
    return Response({"detail": "Пароль успешно изменён."})
