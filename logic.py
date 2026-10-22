"""Geschäftslogik: Pausenabzug nach ArbZG §4, Feiertage Sachsen-Anhalt
und Monatsauswertung."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
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


# (start, end); end = None heißt: Fenster läuft noch.
Window = tuple[time, Optional[time]]


def _closed(windows: Iterable[Window]) -> list[tuple[time, time]]:
    """Nur abgeschlossene Fenster; laufende zählen erst nach "Ende"."""
    return [(s, e) for s, e in windows if e is not None]


def windows_gross_hours(windows: Iterable[Window]) -> float:
    return sum(gross_hours(s, e) for s, e in _closed(windows))


def windows_break_hours(windows: Iterable[Window]) -> float:
    """Summe der Pausen über alle Zeitfenster eines Tages.

    Die Pause wird je Fenster bestimmt: abgezogen wird nur, wenn ein einzelnes
    Fenster die Schwelle (>6h bzw. >9h) überschreitet. Zwei Fenster à 4h
    ergeben also keinen Abzug.
    """
    return sum(legal_break(gross_hours(s, e)) for s, e in _closed(windows))


def windows_net_hours(windows: Iterable[Window]) -> float:
    return sum(net_hours(gross_hours(s, e)) for s, e in _closed(windows))


QUARTER_MINUTES = 15
_LAST_QUARTER = 23 * 60 + 45


def round_to_quarter(now: datetime) -> time:
    """Rundet auf die nächste Viertelstunde (08:07 -> 08:00, 08:08 -> 08:15).

    Nach 23:52 würde auf 24:00 gerundet; das ist keine gültige Uhrzeit des
    Tages, daher wird auf 23:45 begrenzt.
    """
    minutes = now.hour * 60 + now.minute + now.second / 60
    rounded = int(minutes / QUARTER_MINUTES + 0.5) * QUARTER_MINUTES
    rounded = min(rounded, _LAST_QUARTER)
    return time(rounded // 60, rounded % 60)


def check_clock_start(windows: list[Window], start: time) -> Optional[str]:
    """Darf am Tag ein neues Fenster ab `start` laufen? Fehlermeldung oder None.

    Das laufende Fenster ist nach hinten offen, darf also hinter keinem
    vorhandenen Fenster beginnen.
    """
    if any(e is None for _, e in windows):
        return "Es läuft bereits ein Zeitfenster."
    latest_end = max((e for _, e in windows), default=None)
    if latest_end is not None and start < latest_end:
        return (
            f"Anfang {start:%H:%M} liegt vor dem Ende des letzten Zeitfensters "
            f"({latest_end:%H:%M})."
        )
    return None


def check_clock_end(start: time, end: time) -> Optional[str]:
    if end <= start:
        return (
            f"Ende {end:%H:%M} (gerundet) liegt nicht nach dem Anfang {start:%H:%M} – "
            "Zeitfenster läuft weiter."
        )
    return None


def validate_windows(windows: list[Window]) -> Optional[str]:
    """Prüft Zeitfenster eines Tages; gibt eine Fehlermeldung oder None zurück.

    Fenster dürfen sich berühren (12:00-12:00), aber nicht überlappen.
    """
    if not windows:
        return "Bitte mindestens ein Zeitfenster angeben."
    for s, e in windows:
        if e <= s:
            return "Endzeit muss nach Startzeit liegen."
    ordered = sorted(windows)
    for (_, prev_end), (next_start, _) in zip(ordered, ordered[1:]):
        if next_start < prev_end:
            return "Zeitfenster dürfen sich nicht überschneiden."
    return None


def group_windows_by_date(workdays: Iterable[WorkDay]) -> dict[date, list[Window]]:
    """Fasst WorkDay-Zeilen pro Datum zu sortierten Zeitfenster-Listen zusammen."""
    by_date: dict[date, list[Window]] = {}
    for w in workdays:
        by_date.setdefault(w.date, []).append((w.start_time, w.end_time))
    for windows in by_date.values():
        windows.sort(key=lambda w: w[0])  # end kann None sein -> nur nach Start
    return by_date


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
    # 'work' | 'vacation' | 'sick' | 'holiday' | 'empty' | 'weekend' | 'future'
    # | 'inactive'
    # Arbeit am Wochenende ist 'work' mit target=0, zählt also komplett als
    # Überstunden; das Wochensoll bleibt auf Mo-Fr verteilt.
    # 'future' = leerer Mo-Fr-Tag in der Zukunft (zählt nicht ins Soll, damit
    # er keinen künstlichen Minus-Saldo erzeugt).
    # 'inactive' = Tag vor dem Startdatum der Nutzerin; zählt nicht, auch wenn
    # dort noch Einträge liegen.
    kind: str
    gross: float
    net: float
    target: float
    note: str = ""
    windows: list[Window] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return any(e is None for _, e in self.windows)

    @property
    def start(self) -> Optional[time]:
        return self.windows[0][0] if self.windows else None

    @property
    def end(self) -> Optional[time]:
        return self.windows[-1][1] if self.windows else None

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

    # Übertrag zum Startdatum, falls es in diesem Zeitraum liegt.
    opening_balance: float = 0.0

    @property
    def saldo(self) -> float:
        return self.actual_hours - self.target_hours + self.opening_balance

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


def opening_balance_between(user: User, first: date, last: date) -> float:
    """Übertrag der Nutzerin, wenn ihr Startdatum in [first, last] liegt, sonst 0."""
    start = getattr(user, "start_date", None)
    if start is not None and first <= start <= last:
        return getattr(user, "start_balance", 0.0) or 0.0
    return 0.0


def _inactive_note(has_entry: bool) -> str:
    return "vor Startdatum · Eintrag zählt nicht" if has_entry else "vor Startdatum"


def build_month_summary(
    user: User,
    year: int,
    month: int,
    workdays: Iterable[WorkDay],
    absences: Iterable[Absence],
    today: Optional[date] = None,
) -> MonthSummary:
    """Erzeugt eine Monatsübersicht aus den vorhandenen Einträgen.

    `today` bestimmt, bis zu welchem Tag (inkl.) das Soll in die Summen
    einfließt. Leere Mo-Fr-Tage in der Zukunft (d > today) tragen weder zum
    Soll noch zum Ist bei, damit zukünftige Tage keinen künstlichen
    Minus-Saldo erzeugen. Eingetragene Arbeit/Urlaub/Krank an zukünftigen
    Tagen zählen dagegen normal mit.

    Tage vor `user.start_date` sind 'inactive' und zählen weder ins Soll noch
    ins Ist; liegt das Startdatum im Monat, fließt `user.start_balance` als
    Übertrag in den Saldo ein.
    """
    if today is None:
        today = date.today()
    daily_target = user.daily_target
    start_date = getattr(user, "start_date", None)
    wd_by_date = group_windows_by_date(workdays)
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
        is_future = d > today
        # An Feiertagen entfallen die Soll-Stunden (auch wenn sie auf einen Mo-Fr fallen).
        target = daily_target if (is_weekday and not is_holi) else 0.0

        if start_date is not None and d < start_date:
            has_entry = d in wd_by_date or d in abs_by_date
            days.append(
                DaySummary(
                    d, d.weekday(), "inactive", 0.0, 0.0, 0.0, _inactive_note(has_entry)
                )
            )
        elif d in wd_by_date:
            windows = wd_by_date[d]
            g = windows_gross_hours(windows)
            n = windows_net_hours(windows)
            br = windows_break_hours(windows)
            base_note = (
                f"Pause {br * 60:.0f} min abgezogen"
                if br > 0
                else "keine gesetzl. Pause nötig"
            )
            if is_holi:
                note = f"{base_note} · Feiertag: {hname}"
            elif not is_weekday:
                note = f"{base_note} · Wochenende: zählt als Überstunden"
            else:
                note = base_note
            open_starts = [s for s, e in windows if e is None]
            if open_starts:
                note = f"läuft seit {open_starts[0]:%H:%M} · {note}"
            days.append(
                DaySummary(
                    d, d.weekday(), "work", g, n, target, note, windows=windows,
                )
            )
            actual_total += n
            target_total += target
        elif is_holi:
            days.append(
                DaySummary(d, d.weekday(), "holiday", 0.0, 0.0, target, hname)
            )
            # target == 0
        elif d in abs_by_date:
            a = abs_by_date[d]
            kind = "vacation" if a.kind == Absence.KIND_VACATION else "sick"
            note = "Urlaub" if kind == "vacation" else "Krank"
            days.append(
                DaySummary(d, d.weekday(), kind, 0.0, target, target, note)
            )
            actual_total += target
            target_total += target
        elif is_future and is_weekday:
            days.append(
                DaySummary(d, d.weekday(), "future", 0.0, 0.0, target, "noch offen")
            )
            # Bewusst kein target_total += target: zukünftige leere Werktage
            # erzeugen kein Minus im Saldo.
        else:
            kind = "weekend" if not is_weekday else "empty"
            days.append(
                DaySummary(d, d.weekday(), kind, 0.0, 0.0, target, "")
            )
            target_total += target

    first_day, last_day = date(year, month, 1), date(year, month, last)
    opening = opening_balance_between(user, first_day, last_day)
    if start_date is not None and first_day <= start_date <= last_day:
        start_day = days[start_date.day - 1]
        transfer = f"Übertrag {opening:+.2f} h"
        start_day.note = f"{transfer} · {start_day.note}" if start_day.note else transfer

    return MonthSummary(
        user=user,
        year=year,
        month=month,
        days=days,
        target_hours=target_total,
        actual_hours=actual_total,
        opening_balance=opening,
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

    # Übertrag zum Startdatum, falls es in diesem Zeitraum liegt.
    opening_balance: float = 0.0

    @property
    def saldo(self) -> float:
        return self.actual_hours - self.target_hours + self.opening_balance


def build_year_summary(
    user: User,
    year: int,
    workdays: Iterable[WorkDay],
    absences: Iterable[Absence],
    today: Optional[date] = None,
) -> YearSummary:
    """Aggregiert Soll/Ist/Saldo sowie Urlaubs- und Krankentage über das gesamte Jahr.

    Logik identisch zu build_month_summary:
    - Mo-Fr ohne Feiertag: target = daily_target
    - Wochenende oder Feiertag: target = 0
    - Arbeitstag: actual += Summe der Netto-Stunden aller Zeitfenster
    - Urlaub/Krank: actual += target (zählt als erfüllt)
    - Leerer Mo-Fr-Tag in der Zukunft (d > today): zählt nicht ins Soll.
    - Tag vor user.start_date: zählt gar nicht; der Übertrag fließt ein, wenn
      das Startdatum in diesem Jahr liegt.
    """
    if today is None:
        today = date.today()
    daily_target = user.daily_target
    start_date = getattr(user, "start_date", None)
    wd_by_date = group_windows_by_date(workdays)
    abs_by_date = {a.date: a for a in absences}

    target_total = 0.0
    actual_total = 0.0
    vacation = 0
    sick = 0
    worked = 0

    d = date(year, 1, 1)
    if start_date is not None and start_date > d:
        d = start_date
    end_exclusive = date(year + 1, 1, 1)
    one_day = timedelta(days=1)
    while d < end_exclusive:
        is_weekday = d.weekday() < 5
        is_holi = is_holiday(d)
        is_future = d > today
        target = daily_target if (is_weekday and not is_holi) else 0.0

        if d in wd_by_date:
            actual_total += windows_net_hours(wd_by_date[d])
            target_total += target
            worked += 1
        elif is_holi:
            pass  # target == 0
        elif d in abs_by_date:
            a = abs_by_date[d]
            actual_total += target
            target_total += target
            if a.kind == Absence.KIND_VACATION:
                vacation += 1
            else:
                sick += 1
        elif is_future and is_weekday:
            pass  # leerer Werktag in der Zukunft: kein Soll-Beitrag
        else:
            target_total += target

        d += one_day

    return YearSummary(
        user=user,
        year=year,
        target_hours=target_total,
        actual_hours=actual_total,
        vacation_days=vacation,
        sick_days=sick,
        worked_days=worked,
        opening_balance=opening_balance_between(
            user, date(year, 1, 1), date(year, 12, 31)
        ),
    )


# Kleine selbsttestende Asserts (laufen beim Import einmal durch).
assert legal_break(5.0) == 0.0
assert legal_break(6.5) == 0.5
assert legal_break(9.5) == 0.75
assert net_hours(8.0) == 7.5
assert net_hours(10.0) == 9.25
assert net_hours(5.0) == 5.0
assert gross_hours(time(9, 0), time(17, 0)) == 8.0
# Pause je Zeitfenster: 2x4h -> kein Abzug, 7h + 2h -> 30 min nur auf das 7h-Fenster.
assert windows_net_hours([(time(8, 0), time(12, 0)), (time(13, 0), time(17, 0))]) == 8.0
assert windows_net_hours([(time(8, 0), time(15, 0)), (time(16, 0), time(18, 0))]) == 8.5
assert validate_windows([(time(8, 0), time(12, 0)), (time(11, 0), time(14, 0))]) is not None
assert validate_windows([(time(8, 0), time(12, 0)), (time(12, 0), time(14, 0))]) is None
assert round_to_quarter(datetime(2026, 5, 11, 8, 7)) == time(8, 0)
assert round_to_quarter(datetime(2026, 5, 11, 8, 8)) == time(8, 15)
assert round_to_quarter(datetime(2026, 5, 11, 23, 59)) == time(23, 45)
assert windows_net_hours([(time(8, 0), time(12, 0)), (time(13, 0), None)]) == 4.0
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


# --- Saldo-Stichtag-Logik: zukünftige leere Werktage zählen nicht ins Soll. ---
class _FakeUser:
    weekly_hours = 40.0
    daily_target = 8.0


_u = _FakeUser()
# Mai 2026: Mo 11.5. als heutiger Stichtag. Mi 13.5. ist leer und in der Zukunft.
_sm = build_month_summary(_u, 2026, 5, [], [], today=date(2026, 5, 11))
_by_date = {d.date: d for d in _sm.days}
assert _by_date[date(2026, 5, 13)].kind == "future"
assert _by_date[date(2026, 5, 12)].kind == "future"  # Di in der Zukunft
assert _by_date[date(2026, 5, 11)].kind == "empty"   # heute, leer -> Minus zählt
assert _by_date[date(2026, 5, 8)].kind == "empty"    # Fr letzte Woche, leer
assert _by_date[date(2026, 5, 14)].kind == "holiday"  # Christi Himmelfahrt
# target_total: Mo-Fr <= 11.5. ohne Feiertag = 1.5., 4.5., 5.5., 6.5., 7.5., 8.5., 11.5.
# (1.5. ist Tag der Arbeit -> Feiertag, daher target=0)
# also 6 Werktage * 8h = 48h
assert _sm.target_hours == 48.0, _sm.target_hours
assert _sm.actual_hours == 0.0
assert _sm.saldo == -48.0
# Zukünftige Tage haben Soll-Anzeige (für die Zelle), aber kein target_total-Beitrag.
assert _by_date[date(2026, 5, 13)].target == 8.0
# Wenn aber bereits ein Workday in der Zukunft eingetragen ist, zählt er normal.
from types import SimpleNamespace as _NS
_future_wd = _NS(date=date(2026, 5, 13), start_time=time(9, 0), end_time=time(17, 30))
_sm2 = build_month_summary(_u, 2026, 5, [_future_wd], [], today=date(2026, 5, 11))
_d13 = next(d for d in _sm2.days if d.date == date(2026, 5, 13))
assert _d13.kind == "work"
assert _sm2.target_hours == 48.0 + 8.0  # +13.5.
assert abs(_sm2.actual_hours - 8.0) < 1e-9
# Jahresübersicht: zukünftige leere Werktage tragen nicht zum Soll bei.
_sy = build_year_summary(_u, 2026, [], [], today=date(2026, 5, 11))
_sy_full = build_year_summary(_u, 2026, [], [], today=date(2026, 12, 31))
assert _sy.target_hours < _sy_full.target_hours
# Mai-Anteil im Jahressoll muss zu den oben berechneten 48h passen.
assert _sy.target_hours > 48.0 - 1e-9
