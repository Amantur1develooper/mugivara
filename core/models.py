from django.db import models
from django.conf import settings
from django.db import models
from django.utils import timezone
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Restaurant(TimeStampedModel):
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True)
    logo = models.ImageField(upload_to="restaurants/logos/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    about_ru = models.TextField(blank=True, default="")
    about_ky = models.TextField(blank=True, default="")
    about_en = models.TextField(blank=True, default="")
    def __str__(self):
        return self.name_ru

class Branch(TimeStampedModel):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="branches")
    
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    
    address = models.CharField(max_length=300, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    delivery_enabled = models.BooleanField(default=False)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    is_open_24h = models.BooleanField(default=False)
    open_time = models.TimeField(null=True, blank=True)   # например 09:00
    close_time = models.TimeField(null=True, blank=True)  # например 22:00
    cover_photo = models.ImageField(upload_to="branches/covers/", blank=True, null=True)

    def __str__(self):
        return f"{self.restaurant.name_ru} — {self.name_ru}"
    def is_open_now(self) -> bool:
        if not self.is_active:
            return False
        if self.is_open_24h:
            return True
        if not self.open_time or not self.close_time:
            return False

        now = timezone.localtime()
        t = now.time()

        # обычный режим (09:00-22:00)
        if self.open_time < self.close_time:
            return self.open_time <= t < self.close_time
        # через полночь (18:00-02:00)
        return t >= self.open_time or t < self.close_time

class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"
        KITCHEN = "kitchen", "Kitchen"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices)

    class Meta:
        unique_together = ("user", "restaurant", "role")

    def __str__(self):
        return f"{self.user} -> {self.restaurant} ({self.role})"
