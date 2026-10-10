from django.db import models


class SurveyResponse(models.Model):
    """Ответ на опрос «Customer discovery» для заведений — узнаём, как сейчас
    принимают заказы, что болит, и насколько интересен Webordo. Публичная
    форма: public_site.views.survey_page. Анализ ответов: dashboard.views.survey_results
    (только для staff/superuser)."""

    restaurant_name = models.CharField("Заведение / имя", max_length=150, blank=True, default="")
    phone = models.CharField("Телефон", max_length=32, blank=True, default="")

    q1 = models.TextField(
        "Как сейчас принимаете заказы и управляете меню?", blank=True, default="")
    q2 = models.TextField(
        "Что больше всего не нравится в этом процессе?", blank=True, default="")
    q3 = models.TextField(
        "Насколько сильно эти проблемы влияют на работу и доход?", blank=True, default="")
    q4 = models.TextField(
        "Как сейчас решаете эти проблемы?", blank=True, default="")

    score = models.PositiveSmallIntegerField(
        "Оценка интереса к Webordo (1-10)",
        help_text="1 — совсем не нужна, 10 — подключились бы прямо сейчас.",
    )

    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        verbose_name = "Ответ опроса"
        verbose_name_plural = "Ответы опроса"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.restaurant_name or 'Без названия'} — {self.score}/10"
