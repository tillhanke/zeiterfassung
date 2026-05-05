"""Geschäftslogik: Pausenabzug nach ArbZG §4, Feiertage Sachsen-Anhalt
und Monatsauswertung."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, time, timedelta
from functools import lru_cache
from typing import Iterable, Optional

from models import Absence, User, WorkDay


def gross_hours(start: time, end: time) -> float:
    """Bruttoarbeitszeit in Stunden zwischen start und end (gleicher Tag).

    Bei end <= start wird 0 zurückgegeben (ungültig). Über-Mitternacht-Schichten
    werden in dieser Version nicht unterstützt.
    """
    if end <= start:
        return 0.0
    delta = (
        timedelta(hours=end.hour, minutes=end.minute, seconds=end.second)
        - timedelta(hours=start.hour, minutes=start.minute, seconds=start.second)
    )
    return delta.total_seconds() / 3600.0


def legal_break(gross: float) -> float:
    """Gesetzliche Mindestpause (Stunden) gemäß ArbZG §4.

    >6h Arbeit -> 30 Minuten, >9h -> 45 Minuten.
    """
    if gross > 9:
        return 0.75
    if gross > 6:
        return 0.5
    return 0.0


def net_hours(gross: float) -> float:
    """Nettoarbeitszeit nach Abzug der gesetzlichen Mindestpause."""
    return max(0.0, gross - legal_break(gross))


def workday_net_hours(wd: WorkDay) -> float:
    return net_hours(gross_hours(wd.start_time, wd.end_time))


def working_days_in_month(year: int, month: int) -> list[date]:
    """Alle Werktage Mo-Fr im Monat (ohne Berücksichtigung von Feiertagen)."""
    _, last = calendar.monthrange(year, month)
    days: list[date] = []
    for day in range(1, last + 1):
        d = date(year, month, day)
        if d.weekday() < 5:  # 0=Mo .. 4=Fr
            days.append(d)
    return days


# ---------------------------------------------------------------------------
# Feiertage Sachsen-Anhalt
# ---------------------------------------------------------------------------


def _easter_sunday(year: int) -> date:
    """Ostersonntag nach dem anonymen Gregorianischen Algorithmus (Meeus)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


@lru_cache(maxsize=64)
def holidays_sachsen_anhalt(year: int) -> dict[date, str]:
    """Gesetzliche Feiertage in Sachsen-Anhalt für das gegebene Jahr.

    Quelle: Feiertagsgesetz Sachsen-Anhalt (FeiertG LSA). Sachsen-Anhalt hat
    weder Fronleichnam, Allerheiligen, Buß- und Bettag noch Frauentag als
    gesetzlichen Feiertag, dafür aber den Reformationstag.
    """
    easter = _easter_sunday(year)
    holidays: dict[date, str] = {
        date(year, 1, 1): "Neujahr",
        date(year, 1, 6): "Heilige Drei Könige",
        easter - timedelta(days=2): "Karfreitag",
        easter + timedelta(days=1): "Ostermontag",
        date(year, 5, 1): "Tag der Arbeit",
        easter + timedelta(days=39): "Christi Himmelfahrt",
        easter + timedelta(days=50): "Pfingstmontag",
        date(year, 10, 3): "Tag der Deutschen Einheit",
        date(year, 10, 31): "Reformationstag",
        date(year, 12, 25): "1. Weihnachtstag",
        date(year, 12, 26): "2. Weihnachtstag",
    }
    return holidays


def holiday_name(d: date) -> Optional[str]:
    """Name des Feiertags, falls d ein gesetzlicher Feiertag in Sachsen-Anhalt ist."""
    return holidays_sachsen_anhalt(d.year).get(d)


def is_holiday(d: date) -> bool:
    return holiday_name(d) is not None


@dataclass
class DaySummary:
    date: date
    weekday: int  # 0=Mo
    kind: str  # 'work' | 'vacation' | 'sick' | 'holiday' | 'empty' | 'weekend'
    gross: float
    net: float
    target: float
    note: str = ""

    @property
    def diff(self) -> float:
        return self.net - self.target


@dataclass
class MonthSummary:
    user: User
    year: int
    month: int
    days: list[DaySummary]
    target_hours: float
    actual_hours: float

    @property
    def saldo(self) -> float:
        return self.actual_hours - self.target_hours

    @property
    def vacation_days(self) -> int:
        return sum(1 for d in self.days if d.kind == "vacation")

    @property
    def sick_days(self) -> int:
        return sum(1 for d in self.days if d.kind == "sick")

    @property
    def worked_days(self) -> int:
        return sum(1 for d in self.days if d.kind == "work")

    @property
    def holiday_days(self) -> int:
        return sum(1 for d in self.days if d.kind == "holiday")


def build_month_summary(
    user: User,
    year: int,
    month: int,
    workdays: Iterable[WorkDay],
    absences: Iterable[Absence],
) -> MonthSummary:
    """Erzeugt eine Monatsübersicht aus den vorhandenen Einträgen."""
    daily_target = user.daily_target
    wd_by_date = {w.date: w for w in workdays}
    abs_by_date = {a.date: a for a in absences}

    _, last = calendar.monthrange(year, month)
    days: list[DaySummary] = []
    target_total = 0.0
    actual_total = 0.0

    for day in range(1, last + 1):
        d = date(year, month, day)
        is_weekday = d.weekday() < 5
        hname = holiday_name(d)
        is_holi = hname is not None
        # An Feiertagen entfallen die Soll-Stunden (auch wenn sie auf einen Mo-Fr fallen).
        target = daily_target if (is_weekday and not is_holi) else 0.0

        if d in wd_by_date:
            wd = wd_by_date[d]
            g = gross_hours(wd.start_time, wd.end_time)
            n = net_hours(g)
            base_note = (
                f"Pause {legal_break(g) * 60:.0f} min abgezogen"
                if legal_break(g) > 0
                else "keine gesetzl. Pause nötig"
            )
            note = f"{base_note} · Feiertag: {hname}" if is_holi else base_note
            days.append(
                DaySummary(d, d.weekday(), "work", g, n, target, note)
            )
            actual_total += n
        elif is_holi:
            days.append(
                DaySummary(d, d.weekday(), "holiday", 0.0, 0.0, target, hname)
            )
        elif d in abs_by_date:
            a = abs_by_date[d]
            kind = "vacation" if a.kind == Absence.KIND_VACATION else "sick"
            note = "Urlaub" if kind == "vacation" else "Krank"
            days.append(
                DaySummary(d, d.weekday(), kind, 0.0, target, target, note)
            )
            actual_total += target
        else:
            kind = "weekend" if not is_weekday else "empty"
            days.append(
                DaySummary(d, d.weekday(), kind, 0.0, 0.0, target, "")
            )

        target_total += target

    return MonthSummary(
        user=user,
        year=year,
        month=month,
        days=days,
        target_hours=target_total,
        actual_hours=actual_total,
    )


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """Gibt (year, month) verschoben um delta Monate zurück."""
    idx = (year * 12 + (month - 1)) + delta
    return idx // 12, idx % 12 + 1


# ---------------------------------------------------------------------------
# Jahresübersicht
# ---------------------------------------------------------------------------


@dataclass
class YearSummary:
    user: User
    year: int
    target_hours: float
    actual_hours: float
    vacation_days: int
    sick_days: int
    worked_days: int

    @property
    def saldo(self) -> float:
        return self.actual_hours - self.target_hours


def build_year_summary(
    user: User,
    year: int,
    workdays: Iterable[WorkDay],
    absences: Iterable[Absence],
) -> YearSummary:
    """Aggregiert Soll/Ist/Saldo sowie Urlaubs- und Krankentage über das gesamte Jahr.

    Logik identisch zu build_month_summary, aber ohne Tagesliste:
    - Mo-Fr ohne Feiertag: target = daily_target
    - Wochenende oder Feiertag: target = 0
    - Arbeitstag: actual += net_hours(gross)
    - Urlaub/Krank: actual += target (zählt als erfüllt)
    """
    daily_target = user.daily_target
    wd_by_date = {w.date: w for w in workdays}
    abs_by_date = {a.date: a for a in absences}

    target_total = 0.0
    actual_total = 0.0
    vacation = 0
    sick = 0
    worked = 0

    d = date(year, 1, 1)
    end_exclusive = date(year + 1, 1, 1)
    one_day = timedelta(days=1)
    while d < end_exclusive:
        is_weekday = d.weekday() < 5
        is_holi = is_holiday(d)
        target = daily_target if (is_weekday and not is_holi) else 0.0
        target_total += target

        if d in wd_by_date:
            wd = wd_by_date[d]
            actual_total += net_hours(gross_hours(wd.start_time, wd.end_time))
            worked += 1
        elif is_holi:
            pass  # Feiertag: kein Soll, kein zusätzlicher Ist-Beitrag
        elif d in abs_by_date:
            a = abs_by_date[d]
            actual_total += target
            if a.kind == Absence.KIND_VACATION:
                vacation += 1
            else:
                sick += 1

        d += one_day

    return YearSummary(
        user=user,
        year=year,
        target_hours=target_total,
        actual_hours=actual_total,
        vacation_days=vacation,
        sick_days=sick,
        worked_days=worked,
    )


# Kleine selbsttestende Asserts (laufen beim Import einmal durch).
assert legal_break(5.0) == 0.0
assert legal_break(6.5) == 0.5
assert legal_break(9.5) == 0.75
assert net_hours(8.0) == 7.5
assert net_hours(10.0) == 9.25
assert net_hours(5.0) == 5.0
assert gross_hours(time(9, 0), time(17, 0)) == 8.0
assert shift_month(2026, 1, -1) == (2025, 12)
assert shift_month(2026, 12, 1) == (2027, 1)
# Bekannte Ostersonntage zur Verifikation des Algorithmus.
assert _easter_sunday(2024) == date(2024, 3, 31)
assert _easter_sunday(2025) == date(2025, 4, 20)
assert _easter_sunday(2026) == date(2026, 4, 5)
# Sachsen-Anhalt: Reformationstag muss enthalten sein, Fronleichnam nicht.
_h2026 = holidays_sachsen_anhalt(2026)
assert _h2026[date(2026, 10, 31)] == "Reformationstag"
assert _h2026[date(2026, 1, 1)] == "Neujahr"
assert _h2026[date(2026, 1, 6)] == "Heilige Drei Könige"
assert _h2026[date(2026, 5, 14)] == "Christi Himmelfahrt"  # Ostern 2026 + 39
assert date(2026, 6, 4) not in _h2026  # Fronleichnam (in LSA kein Feiertag)
assert holiday_name(date(2026, 12, 25)) == "1. Weihnachtstag"
assert is_holiday(date(2026, 5, 1)) is True
assert is_holiday(date(2026, 1, 6)) is True
assert is_holiday(date(2026, 5, 4)) is False
