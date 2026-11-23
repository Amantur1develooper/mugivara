# -*- coding: utf-8 -*-
"""Проверки шаблонов, которые нельзя доверять внимательности.

Django-комментарий {# … #} — однострочный: если его растянуть на две
строки, он не считается комментарием и целиком вылезает на страницу
пользователю. На этом в проекте обожглись пять раз подряд, в том числе
прямо в меню кабинета и в списке клиентов, поэтому теперь за этим следит
тест, а не глаз.
"""
import os
import re

from django.conf import settings
from django.test import SimpleTestCase


def _template_files():
    for root in [os.path.join(settings.BASE_DIR, "templates")]:
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if name.endswith((".html", ".txt")):
                    yield os.path.join(dirpath, name)


class MultilineCommentsTests(SimpleTestCase):
    def test_no_multiline_hash_comments(self):
        """{# … #} не должен переноситься на следующую строку."""
        bad = []
        for path in _template_files():
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            for m in re.finditer(r"\{#", src):
                tail = src[m.start():]
                close = tail.find("#}")
                newline = tail.find("\n")
                if close == -1 or (newline != -1 and newline < close):
                    line = src[:m.start()].count("\n") + 1
                    rel = os.path.relpath(path, settings.BASE_DIR)
                    bad.append(f"{rel}:{line}")

        self.assertEqual(
            bad, [],
            "Многострочный {# … #} попадёт на страницу текстом. "
            "Используйте {% comment %}…{% endcomment %}:\n  " + "\n  ".join(bad))
