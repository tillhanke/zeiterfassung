"""Tests für die reine Geschäftslogik (logic.py).

Diese Tests sind komplett DB-frei und nutzen einen minimalen User-Stub.
Sie laufen damit auch ohne App-Kontext.
"""
from __future__ import annotations

import calendar
from datetime import date, time
from types import SimpleNamespace

import pytest

import logic
from logic import (
    _easter_sunday,
    build_month_summary,
    build_year_summary,
    gross_hours,
    holiday_name,
    holidays_sachsen_anhalt,
    is_holiday,
    legal_break,
    net_hours,
    shift_month,
    validate_windows,
    windows_break_hours,
    windows_net_hours,
    working_days_in_month,
    workday_net_hours,
)


def _user(weekly_hours: float = 40.0):
    """Minimaler User-Stub mit den von logic.py genutzten Feldern."""
    return SimpleNamespace(weekly_hours=weekly_hours, daily_target=weekly_hours / 5.0)


def _wd(d: date, start: time, end: time):
    return SimpleNamespace(date=d, start_time=start, end_time=end)


def _abs(d: date, kind: str):
    return SimpleNamespace(date=d, kind=kind)


# ---------------------------------------------------------------------------
# Brutto / Pause / Netto
# ---------------------------------------------------------------------------


class TestGrossHours:
    def test_basic_eight_hours(self):
        assert gross_hours(time(9, 0), time(17, 0)) == 8.0

    def test_fractional(self):
        assert gross_hours(time(9, 0), time(9, 30)) == 0.5

    def test_end_equal_start_returns_zero(self):
        assert gross_hours(time(10, 0), time(10, 0)) == 0.0

    def test_end_before_start_returns_zero(self):
        # Über-Mitternacht-Schichten werden bewusst nicht unterstützt.
        assert gross_hours(time(22, 0), time(6, 0)) == 0.0


class TestLegalBreak:
    @pytest.mark.parametrize(
        "gross,expected",
        [
            (0.0, 0.0),
            (5.99, 0.0),
            (6.0, 0.0),           # genau 6 h: keine Pflichtpause
            (6.0001, 0.5),
            (8.0, 0.5),
            (9.0, 0.5),           # genau 9 h: noch 30 min
            (9.0001, 0.75),
            (12.0, 0.75),
        ],
    )
    def test_break_thresholds(self, gross, expected):
        assert legal_break(gross) == expected


class TestNetHours:
    def test_below_threshold_no_break(self):
        assert net_hours(5.0) == 5.0

    def test_eight_hours_minus_half(self):
        assert net_hours(8.0) == 7.5

    def test_ten_hours_minus_45min(self):
        assert net_hours(10.0) == 9.25

    def test_never_negative(self):
        assert net_hours(0.0) == 0.0


class TestWorkdayNetHours:
    def test_uses_underlying_funcs(self):
        wd = _wd(date(2026, 5, 11), time(9, 0), time(17, 30))
        assert workday_net_hours(wd) == pytest.approx(8.0)


# ---------------------------------------------------------------------------
# Werktage / Feiertage
# ---------------------------------------------------------------------------


class TestWindows:
    def test_two_short_windows_no_break(self):
        # 2x4h = 8h brutto, aber kein einzelnes Fenster > 6h -> keine Pause.
        windows = [(time(8, 0), time(12, 0)), (time(13, 0), time(17, 0))]
        assert windows_break_hours(windows) == 0.0
        assert windows_net_hours(windows) == 8.0

    def test_break_only_on_long_window(self):
        # 7h-Fenster -> 30 min, 2h-Fenster -> 0.
        windows = [(time(7, 0), time(14, 0)), (time(15, 0), time(17, 0))]
        assert windows_break_hours(windows) == 0.5
        assert windows_net_hours(windows) == pytest.approx(8.5)

    def test_break_summed_over_windows(self):
        windows = [(time(0, 0), time(6, 30)), (time(7, 0), time(16, 30))]
        # 6.5h -> 30 min, 9.5h -> 45 min
        assert windows_break_hours(windows) == pytest.approx(1.25)

    def test_single_window_matches_net_hours(self):
        assert windows_net_hours([(time(9, 0), time(17, 30))]) == net_hours(8.5)

    def test_validate_ok(self):
        assert validate_windows([(time(8, 0), time(12, 0)), (time(13, 0), time(17, 0))]) is None

    def test_validate_touching_windows_ok(self):
        assert validate_windows([(time(8, 0), time(12, 0)), (time(12, 0), time(17, 0))]) is None

    def test_validate_overlap(self):
        err = validate_windows([(time(13, 0), time(17, 0)), (time(8, 0), time(13, 30))])
        assert "überschneiden" in err

    def test_validate_end_before_start(self):
        assert "nach Startzeit" in validate_windows([(time(12, 0), time(8, 0))])

    def test_validate_empty(self):
        assert validate_windows([]) is not None


class TestWorkingDaysInMonth:
    def test_may_2026(self):
        days = working_days_in_month(2026, 5)
        # alle Tage Mo-Fr im Mai 2026
        assert len(days) == 21
        for d in days:
            assert d.weekday() < 5

    def test_february_2026(self):
        # Feb 2026: 28 Tage, davon 20 Werktage
        days = working_days_in_month(2026, 2)
        assert len(days) == 20

    def test_returns_only_dates_in_month(self):
        for d in working_days_in_month(2026, 7):
            assert d.year == 2026 and d.month == 7


class TestEaster:
    @pytest.mark.parametrize(
        "year,expected",
        [
            (2024, date(2024, 3, 31)),
            (2025, date(2025, 4, 20)),
            (2026, date(2026, 4, 5)),
            (2027, date(2027, 3, 28)),
        ],
    )
    def test_known_easters(self, year, expected):
        assert _easter_sunday(year) == expected


class TestHolidaysSachsenAnhalt:
    def test_contains_neujahr(self):
        h = holidays_sachsen_anhalt(2026)
        assert h[date(2026, 1, 1)] == "Neujahr"

    def test_contains_reformationstag(self):
        h = holidays_sachsen_anhalt(2026)
        assert h[date(2026, 10, 31)] == "Reformationstag"

    def test_does_not_contain_fronleichnam(self):
        # Fronleichnam ist in Sachsen-Anhalt KEIN gesetzlicher Feiertag.
        h = holidays_sachsen_anhalt(2026)
        assert date(2026, 6, 4) not in h

    def test_easter_dependent_holidays(self):
        h = holidays_sachsen_anhalt(2026)
        # Ostern 2026 = 5.4. -> Karfreitag 3.4., Ostermontag 6.4.,
        # Christi Himmelfahrt 14.5., Pfingstmontag 25.5.
        assert h[date(2026, 4, 3)] == "Karfreitag"
        assert h[date(2026, 4, 6)] == "Ostermontag"
        assert h[date(2026, 5, 14)] == "Christi Himmelfahrt"
        assert h[date(2026, 5, 25)] == "Pfingstmontag"

    def test_eleven_holidays_per_year(self):
        assert len(holidays_sachsen_anhalt(2026)) == 11

    def test_works_for_different_years(self):
        # 2024: Ostern 31.3. -> Karfreitag 29.3.
        h = holidays_sachsen_anhalt(2024)
        assert h[date(2024, 3, 29)] == "Karfreitag"


class TestHolidayHelpers:
    def test_holiday_name(self):
        assert holiday_name(date(2026, 12, 25)) == "1. Weihnachtstag"
        assert holiday_name(date(2026, 5, 4)) is None

    def test_is_holiday(self):
        assert is_holiday(date(2026, 5, 1)) is True
        assert is_holiday(date(2026, 5, 4)) is False


# ---------------------------------------------------------------------------
# Monats-Verschiebung
# ---------------------------------------------------------------------------


class TestShiftMonth:
    def test_backward_year_boundary(self):
        assert shift_month(2026, 1, -1) == (2025, 12)

    def test_forward_year_boundary(self):
        assert shift_month(2026, 12, 1) == (2027, 1)

    def test_no_shift(self):
        assert shift_month(2026, 5, 0) == (2026, 5)

    def test_large_shift(self):
        assert shift_month(2026, 5, 12) == (2027, 5)
        assert shift_month(2026, 5, -24) == (2024, 5)


# ---------------------------------------------------------------------------
# Monats-Übersicht
# ---------------------------------------------------------------------------


class TestBuildMonthSummary:
    """Mai 2026: 1.5. ist Tag der Arbeit (Fr, Feiertag),
    14.5. Christi Himmelfahrt (Do, Feiertag), 25.5. Pfingstmontag (Mo, Feiertag).
    Werktage Mo-Fr im Mai 2026: 21; davon 3 Feiertage -> 18 echte Soll-Tage.
    """

    def test_empty_past_month_full_target(self):
        # 'today' liegt nach Monatsende: voller Monat fließt ins Soll
        sm = build_month_summary(_user(), 2026, 5, [], [], today=date(2026, 6, 30))
        # 18 Werktage * 8h = 144h
        assert sm.target_hours == pytest.approx(18 * 8.0)
        assert sm.actual_hours == 0.0
        assert sm.saldo == pytest.approx(-18 * 8.0)
        assert len(sm.days) == 31

    def test_future_empty_workdays_get_future_kind(self):
        sm = build_month_summary(_user(), 2026, 5, [], [], today=date(2026, 5, 11))
        by_date = {d.date: d for d in sm.days}
        # 12.5. (Di) ist in der Zukunft, leer -> future
        assert by_date[date(2026, 5, 12)].kind == "future"
        # 11.5. (Mo) = heute, leer -> empty (zählt ins Soll als verpasst)
        assert by_date[date(2026, 5, 11)].kind == "empty"
        # 14.5. (Do, Christi Himmelfahrt) -> holiday (auch wenn in Zukunft)
        assert by_date[date(2026, 5, 14)].kind == "holiday"
        # 1.5. (Fr, Tag der Arbeit, in Vergangenheit) -> holiday
        assert by_date[date(2026, 5, 1)].kind == "holiday"
        # 2.5. (Sa) -> weekend
        assert by_date[date(2026, 5, 2)].kind == "weekend"

    def test_future_days_do_not_contribute_to_target(self):
        sm = build_month_summary(_user(), 2026, 5, [], [], today=date(2026, 5, 11))
        # Werktage Mo-Fr <= 11.5. ohne Feiertag:
        # 1.5. (Tag der Arbeit, Feiertag) -> nicht
        # 4.5., 5.5., 6.5., 7.5., 8.5., 11.5. = 6 Tage
        assert sm.target_hours == pytest.approx(6 * 8.0)
        assert sm.actual_hours == 0.0
        assert sm.saldo == pytest.approx(-48.0)

    def test_full_workdays_match_target(self):
        wds = [
            _wd(date(2026, 5, day), time(9, 0), time(17, 30))
            for day in (4, 5, 6, 7, 8, 11)
        ]
        sm = build_month_summary(_user(), 2026, 5, wds, [], today=date(2026, 5, 11))
        assert sm.actual_hours == pytest.approx(6 * 8.0)
        assert sm.target_hours == pytest.approx(6 * 8.0)
        assert abs(sm.saldo) < 1e-9
        assert sm.worked_days == 6

    def test_vacation_counts_as_fulfilled(self):
        absences = [_abs(date(2026, 5, 11), "vacation")]
        sm = build_month_summary(_user(), 2026, 5, [], absences, today=date(2026, 5, 11))
        # 11.5. ist Urlaub -> actual += 8, target += 8.
        # Übrige 5 Werktage (4.-8.5.) sind leer + Vergangenheit -> target += 5*8.
        assert sm.target_hours == pytest.approx(6 * 8.0)
        assert sm.actual_hours == pytest.approx(8.0)
        assert sm.vacation_days == 1

    def test_sick_counts_as_fulfilled(self):
        absences = [_abs(date(2026, 5, 11), "sick")]
        sm = build_month_summary(_user(), 2026, 5, [], absences, today=date(2026, 5, 11))
        assert sm.sick_days == 1
        assert sm.actual_hours == pytest.approx(8.0)

    def test_workday_on_holiday_target_zero(self):
        # 14.5. ist Christi Himmelfahrt (Do). Wenn jemand trotzdem arbeitet,
        # zählt nur das Ist, nicht das Soll.
        wds = [_wd(date(2026, 5, 14), time(9, 0), time(13, 0))]
        sm = build_month_summary(_user(), 2026, 5, wds, [], today=date(2026, 5, 31))
        # Mai 2026: 18 Soll-Werktage (21 Mo-Fr - 3 Feiertage) * 8h = 144h.
        # Der Feiertag bleibt target=0, auch mit eingetragener Arbeit.
        assert sm.target_hours == pytest.approx(18 * 8.0)
        # 4h netto (unter 6h-Grenze, also keine Pause)
        assert sm.actual_hours == pytest.approx(4.0)

    def test_future_workday_counts(self):
        wds = [_wd(date(2026, 5, 15), time(9, 0), time(17, 30))]
        sm = build_month_summary(_user(), 2026, 5, wds, [], today=date(2026, 5, 11))
        by_date = {d.date: d for d in sm.days}
        assert by_date[date(2026, 5, 15)].kind == "work"
        # 6 vergangene Tage (4.-8., 11.) + 1 future workday = 7*8h
        assert sm.target_hours == pytest.approx(7 * 8.0)
        assert sm.actual_hours == pytest.approx(8.0)

    def test_future_month_zero_target(self):
        sm = build_month_summary(_user(), 2026, 7, [], [], today=date(2026, 5, 11))
        assert sm.target_hours == 0.0
        assert sm.actual_hours == 0.0
        assert sm.saldo == 0.0
        assert {d.kind for d in sm.days} <= {"future", "weekend"}

    def test_diff_property_per_day(self):
        wds = [_wd(date(2026, 5, 11), time(9, 0), time(17, 30))]
        sm = build_month_summary(_user(), 2026, 5, wds, [], today=date(2026, 5, 11))
        by_date = {d.date: d for d in sm.days}
        wday = by_date[date(2026, 5, 11)]
        # net 8h - target 8h = 0
        assert wday.diff == pytest.approx(0.0)

    def test_workday_has_start_and_end_times(self):
        wds = [_wd(date(2026, 5, 11), time(8, 15), time(16, 45))]
        sm = build_month_summary(_user(), 2026, 5, wds, [], today=date(2026, 5, 11))
        by_date = {d.date: d for d in sm.days}
        wday = by_date[date(2026, 5, 11)]
        assert wday.start == time(8, 15)
        assert wday.end == time(16, 45)

    def test_multiple_windows_aggregated_per_day(self):
        wds = [
            _wd(date(2026, 5, 11), time(13, 0), time(17, 0)),
            _wd(date(2026, 5, 11), time(8, 0), time(12, 0)),
        ]
        sm = build_month_summary(_user(), 2026, 5, wds, [], today=date(2026, 5, 11))
        wday = next(d for d in sm.days if d.date == date(2026, 5, 11))
        assert wday.kind == "work"
        assert wday.windows == [(time(8, 0), time(12, 0)), (time(13, 0), time(17, 0))]
        assert wday.start == time(8, 0)
        assert wday.end == time(17, 0)
        assert wday.gross == 8.0
        assert wday.net == 8.0  # keine Pause, da kein Fenster > 6h
        assert "keine gesetzl. Pause" in wday.note
        assert sm.worked_days == 1

    def test_multiple_windows_break_note(self):
        wds = [
            _wd(date(2026, 5, 11), time(7, 0), time(14, 0)),
            _wd(date(2026, 5, 11), time(15, 0), time(17, 0)),
        ]
        sm = build_month_summary(_user(), 2026, 5, wds, [], today=date(2026, 5, 11))
        wday = next(d for d in sm.days if d.date == date(2026, 5, 11))
        assert wday.net == pytest.approx(8.5)
        assert "Pause 30 min" in wday.note

    def test_weekend_work_counts_fully_as_overtime(self):
        # Sa 9.5.2026: Soll 0, Ist = Netto -> komplette Arbeitszeit ist Plus.
        wds = [_wd(date(2026, 5, 9), time(9, 0), time(13, 0))]
        sm = build_month_summary(_user(), 2026, 5, wds, [], today=date(2026, 5, 31))
        sm_without = build_month_summary(_user(), 2026, 5, [], [], today=date(2026, 5, 31))
        sat = next(d for d in sm.days if d.date == date(2026, 5, 9))
        assert sat.kind == "work"
        assert sat.target == 0.0
        assert sat.diff == pytest.approx(4.0)
        assert "Überstunden" in sat.note
        # Monatssoll unverändert (Wochenstunden bleiben auf Mo-Fr verteilt).
        assert sm.target_hours == sm_without.target_hours
        assert sm.saldo == pytest.approx(sm_without.saldo + 4.0)

    def test_weekend_work_break_rule_applies(self):
        wds = [_wd(date(2026, 5, 10), time(8, 0), time(15, 0))]  # So, 7h
        sm = build_month_summary(_user(), 2026, 5, wds, [], today=date(2026, 5, 31))
        sun = next(d for d in sm.days if d.date == date(2026, 5, 10))
        assert sun.net == pytest.approx(6.5)
        assert sun.diff == pytest.approx(6.5)

    def test_non_work_days_have_no_start_end(self):
        absences = [_abs(date(2026, 5, 11), "vacation")]
        sm = build_month_summary(_user(), 2026, 5, [], absences, today=date(2026, 5, 11))
        by_date = {d.date: d for d in sm.days}
        # Urlaubs-, Feiertags-, Wochenend- und leere Tage haben keine Start/Endzeit.
        assert by_date[date(2026, 5, 11)].start is None  # vacation
        assert by_date[date(2026, 5, 11)].end is None
        assert by_date[date(2026, 5, 1)].start is None   # holiday
        assert by_date[date(2026, 5, 2)].start is None   # weekend

    def test_target_per_day_visible_on_future(self):
        """Future-Tage zeigen Soll-Wert (informativ), tragen aber nicht ins target_total bei."""
        sm = build_month_summary(_user(), 2026, 5, [], [], today=date(2026, 5, 11))
        by_date = {d.date: d for d in sm.days}
        future_day = by_date[date(2026, 5, 13)]  # Mi
        assert future_day.kind == "future"
        assert future_day.target == 8.0  # zur Anzeige
        # ... aber nicht im Gesamttotal:
        # (im obigen Test test_future_days_do_not_contribute_to_target abgedeckt)

    def test_weekly_hours_20(self):
        sm = build_month_summary(_user(20.0), 2026, 5, [], [], today=date(2026, 5, 31))
        # daily_target = 4.0, 18 Soll-Werktage -> 72h
        assert sm.target_hours == pytest.approx(72.0)

    def test_holiday_count(self):
        sm = build_month_summary(_user(), 2026, 5, [], [], today=date(2026, 5, 31))
        # Mai 2026: 1.5., 14.5., 25.5. = 3 Feiertage
        assert sm.holiday_days == 3

    def test_default_today_uses_date_today(self, monkeypatch):
        """Ohne today-Argument wird date.today() benutzt."""
        from datetime import date as real_date

        class _FrozenDate(real_date):
            @classmethod
            def today(cls):
                return real_date(2026, 5, 11)

        monkeypatch.setattr(logic, "date", _FrozenDate)
        sm = build_month_summary(_user(), 2026, 5, [], [])
        # Gleiches Resultat wie mit explizitem today
        assert sm.target_hours == pytest.approx(48.0)


# ---------------------------------------------------------------------------
# Jahres-Übersicht
# ---------------------------------------------------------------------------


class TestBuildYearSummaryWindows:
    def test_multiple_windows_count_as_one_worked_day(self):
        wds = [
            _wd(date(2026, 5, 11), time(8, 0), time(12, 0)),
            _wd(date(2026, 5, 11), time(13, 0), time(17, 0)),
        ]
        ys = build_year_summary(_user(), 2026, wds, [], today=date(2026, 1, 1))
        assert ys.worked_days == 1
        assert ys.actual_hours == pytest.approx(8.0)


class TestBuildYearSummaryWeekend:
    def test_weekend_work_adds_overtime_without_target(self):
        wds = [_wd(date(2026, 5, 9), time(9, 0), time(13, 0))]
        with_wd = build_year_summary(_user(), 2026, wds, [], today=date(2026, 12, 31))
        without = build_year_summary(_user(), 2026, [], [], today=date(2026, 12, 31))
        assert with_wd.target_hours == without.target_hours
        assert with_wd.saldo == pytest.approx(without.saldo + 4.0)
        assert with_wd.worked_days == 1


class TestBuildYearSummary:
    def test_past_year_full(self):
        sy = build_year_summary(_user(), 2025, [], [], today=date(2026, 1, 1))
        # 2025 ist komplett Vergangenheit, alle Werktage zählen.
        # Realer Wert ist getestet über die Konsistenz Mai-Anteil.
        assert sy.target_hours > 0
        assert sy.actual_hours == 0.0
        assert sy.saldo == -sy.target_hours

    def test_future_empty_days_skipped(self):
        sy_mid = build_year_summary(_user(), 2026, [], [], today=date(2026, 5, 11))
        sy_full = build_year_summary(_user(), 2026, [], [], today=date(2026, 12, 31))
        assert sy_mid.target_hours < sy_full.target_hours

    def test_workday_in_future_counts(self):
        wds = [_wd(date(2026, 12, 24), time(9, 0), time(17, 30))]
        sy = build_year_summary(_user(), 2026, wds, [], today=date(2026, 5, 11))
        assert sy.actual_hours == pytest.approx(8.0)
        assert sy.worked_days == 1

    def test_vacation_and_sick_counts(self):
        absences = [
            _abs(date(2026, 5, 11), "vacation"),
            _abs(date(2026, 5, 7), "sick"),
        ]
        sy = build_year_summary(_user(), 2026, [], absences, today=date(2026, 5, 11))
        assert sy.vacation_days == 1
        assert sy.sick_days == 1
        # Beide Tage zählen mit voller Soll-Erfüllung in actual.
        assert sy.actual_hours == pytest.approx(2 * 8.0)

    def test_holiday_does_not_contribute(self):
        # Ohne Einträge: target zählt Werktage ohne Feiertag.
        sy = build_year_summary(_user(), 2026, [], [], today=date(2026, 12, 31))
        # Sanity: irgendein positiver Wert
        assert sy.target_hours > 1000  # ~ 2000h für ein volles Jahr
        # Eine Erhöhung durch Feiertag würde > 9*8h zusätzlich kosten.
        # Vergleich mit naivem Werktag-Zählen:
        all_weekdays = sum(
            1
            for m in range(1, 13)
            for d in working_days_in_month(2026, m)
        )
        # 11 Feiertage SA, davon einige auf Sa/So fallen evtl. Konkret 2026:
        # 1.1. Do, 6.1. Di, 3.4. Fr (Karfr), 6.4. Mo, 1.5. Fr, 14.5. Do,
        # 25.5. Mo, 3.10. Sa, 31.10. Sa, 25.12. Fr, 26.12. Sa
        # -> 8 Feiertage fallen auf Mo-Fr.
        assert sy.target_hours == pytest.approx((all_weekdays - 8) * 8.0)


# ---------------------------------------------------------------------------
# Konsistenz: per-day target == target_total für Past-Monate
# ---------------------------------------------------------------------------


def test_per_day_targets_sum_matches_total_for_past_month():
    sm = build_month_summary(_user(), 2026, 3, [], [], today=date(2026, 12, 31))
    summed = sum(d.target for d in sm.days)
    assert summed == pytest.approx(sm.target_hours)


def test_per_day_targets_differ_from_total_when_future_present():
    sm = build_month_summary(_user(), 2026, 5, [], [], today=date(2026, 5, 11))
    summed = sum(d.target for d in sm.days)
    # per-day target wird auch für future-Tage angezeigt -> Summe > target_total.
    assert summed > sm.target_hours
