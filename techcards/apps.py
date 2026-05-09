from django.apps import AppConfig


class TechCardsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "techcards"
    verbose_name = "Техкарты и склад"

    def ready(self):
        import techcards.signals  # noqa
