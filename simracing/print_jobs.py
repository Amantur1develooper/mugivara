"""Receipt content formatting and print job creation for simracing."""
from django.utils import timezone

W = 32  # receipt width in chars (80mm paper ≈ 42 chars, 58mm ≈ 32 chars)
B  = "\x02"  # bold on
b  = "\x03"  # bold off
SEP  = "=" * W
sep  = "-" * W


def _center(text, width=W):
    return text.center(width)


def _row(label, value, width=W):
    """Left-align label, right-align value."""
    space = width - len(label) - len(value)
    return label + " " * max(1, space) + value


def _session_receipt(session):
    from django.utils import timezone as tz
    started = tz.localtime(session.started_at)
    ended   = tz.localtime(session.ends_at)

    weekday_ru = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    date_str = started.strftime(f"%d.%m.%Y ({weekday_ru[started.weekday()]})")

    type_label = dict(session.machine.Type.choices if hasattr(session.machine, 'Type')
                      else []).get(session.machine_type_snapshot, session.machine_type_snapshot)
    # Use machine's get_type_display
    try:
        type_label = session.machine.get_type_display()
    except Exception:
        pass

    lines = [
        SEP,
        B + _center(session.venue.name) + b,
        B + _center(f"ЧЕК #{session.id}") + b,
        SEP,
        _row("Дата:", date_str),
        _row("Время:", started.strftime("%H:%M")),
        sep,
        f"Машина: {session.machine.name}",
        f"Тип: {type_label}",
        _row("Длительность:", f"{session.duration_minutes} мин"),
        _row("Начало:", started.strftime("%H:%M")) + "  " + _row("Конец:", ended.strftime("%H:%M")),
    ]

    if session.customer_name:
        lines.append(sep)
        lines.append(f"Клиент: {session.customer_name}")
    if session.customer_phone:
        lines.append(f"Тел: {session.customer_phone}")

    lines += [
        SEP,
        B + _row("ИТОГО:", f"{int(session.price)} сом") + b,
        SEP,
        _center("Спасибо! Приходите ещё!"),
        SEP,
        "",
    ]
    return "\n".join(lines)


def _appt_receipt(appt):
    weekday_ru = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    date_str = appt.appt_date.strftime(f"%d.%m.%Y ({weekday_ru[appt.appt_date.weekday()]})")

    from .models import Machine
    type_label = dict(Machine.Type.choices).get(appt.machine_type, appt.machine_type)

    dur_per = appt.session_type.duration_minutes if appt.session_type else "?"
    price_per = int(appt.session_type.price) if appt.session_type else "?"

    lines = [
        SEP,
        B + _center(appt.venue.name) + b,
        B + _center(f"ЗАПИСЬ #{appt.id}") + b,
        SEP,
        f"Тип: {type_label}",
        f"Сессия: {dur_per} мин × {appt.quantity} заезд(а)",
        _row("Дата:", date_str),
        _row("Время:", appt.appt_time.strftime("%H:%M")),
        _row("Итог. длит.:", f"{appt.duration_minutes} мин"),
    ]

    if appt.customer_name:
        lines.append(sep)
        lines.append(f"Клиент: {appt.customer_name}")
    if appt.customer_phone:
        lines.append(f"Тел: {appt.customer_phone}")

    lines += [
        SEP,
        B + _row("К ОПЛАТЕ:", f"{int(appt.total_price)} сом") + b,
        SEP,
        _center("Ждём вас!"),
        SEP,
        "",
    ]
    return "\n".join(lines)


def create_session_print_job(session):
    """Create a print job when a live session is closed."""
    from .models import SimRacingPrintConfig, SimRacingPrintJob
    try:
        cfg = SimRacingPrintConfig.objects.get(venue=session.venue, enabled=True)
    except SimRacingPrintConfig.DoesNotExist:
        return None
    content = _session_receipt(session)
    return SimRacingPrintJob.objects.create(
        venue=session.venue,
        session=session,
        content=content,
    )


def create_appt_print_job(appt):
    """Create a print job when an online appointment is confirmed."""
    from .models import SimRacingPrintConfig, SimRacingPrintJob
    try:
        cfg = SimRacingPrintConfig.objects.get(venue=appt.venue, enabled=True)
    except SimRacingPrintConfig.DoesNotExist:
        return None
    content = _appt_receipt(appt)
    return SimRacingPrintJob.objects.create(
        venue=appt.venue,
        appt=appt,
        content=content,
    )
