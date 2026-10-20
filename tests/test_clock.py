"""Tests für die Buttons "Anfang"/"Ende" (Stempeln mit aktueller Uhrzeit)."""
from __future__ import annotations

from datetime import date, datetime, time

import pytest

import app as app_module
import logic
from models import Absence, WorkDay


@pytest.fixture
def freeze_now(monkeypatch):
    """Setzt "jetzt" für app.py (datetime.now / date.today)."""

    def _freeze(now: datetime):
        class FakeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return now

        class FakeDate(date):
            @classmethod
            def today(cls):
                return now.date()

        monkeypatch.setattr(app_module, "datetime", FakeDatetime)
        monkeypatch.setattr(app_module, "date", FakeDate)

    return _freeze


def _windows(app, user_id, d=date(2026, 5, 11)):
    with app.app_context():
        return [
            (w.start_time, w.end_time)
            for w in WorkDay.query.filter_by(user_id=user_id, date=d).order_by(WorkDay.start_time)
        ]


def _start(client, user_id):
    return client.post(f"/user/{user_id}/clock/start", follow_redirects=True)


def _end(client, user_id):
    return client.post(f"/user/{user_id}/clock/end", follow_redirects=True)


class TestRoundToQuarter:
    @pytest.mark.parametrize(
        "hh, mm, expected",
        [
            (8, 0, time(8, 0)),
            (8, 7, time(8, 0)),
            (8, 8, time(8, 15)),
            (8, 22, time(8, 15)),
            (8, 23, time(8, 30)),
            (8, 53, time(9, 0)),
            (0, 3, time(0, 0)),
            (23, 52, time(23, 45)),
            (23, 59, time(23, 45)),
        ],
    )
    def test_rounds_to_nearest_quarter(self, hh, mm, expected):
        assert logic.round_to_quarter(datetime(2026, 5, 11, hh, mm)) == expected


class TestClockStart:
    def test_sets_rounded_start_and_open_window(self, client, login_alice, app, freeze_now):
        freeze_now(datetime(2026, 5, 11, 8, 6))
        r = _start(client, login_alice)
        assert "Anfang 08:00 gesetzt".encode() in r.data
        assert _windows(app, login_alice) == [(time(8, 0), None)]

    def test_double_start_rejected(self, client, login_alice, app, freeze_now):
        freeze_now(datetime(2026, 5, 11, 8, 0))
        _start(client, login_alice)
        freeze_now(datetime(2026, 5, 11, 9, 0))
        r = _start(client, login_alice)
        assert "läuft bereits".encode() in r.data
        assert _windows(app, login_alice) == [(time(8, 0), None)]

    def test_second_window_after_first(self, client, login_alice, app, freeze_now, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(8, 0), time(12, 0))
        freeze_now(datetime(2026, 5, 11, 12, 55))
        _start(client, login_alice)
        assert _windows(app, login_alice) == [(time(8, 0), time(12, 0)), (time(13, 0), None)]

    def test_start_before_existing_end_rejected(self, client, login_alice, app, freeze_now, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(8, 0), time(12, 0))
        freeze_now(datetime(2026, 5, 11, 11, 0))
        r = _start(client, login_alice)
        assert "vor dem Ende".encode() in r.data
        assert len(_windows(app, login_alice)) == 1

    def test_open_window_on_other_day_blocks(self, client, login_alice, app, freeze_now, make_workday):
        make_workday(login_alice, date(2026, 5, 8), time(8, 0), None)
        freeze_now(datetime(2026, 5, 11, 8, 0))
        r = _start(client, login_alice)
        assert b"2026-05-08" in r.data
        assert _windows(app, login_alice) == []

    def test_absence_blocks(self, client, login_alice, app, freeze_now, make_absence):
        make_absence(login_alice, date(2026, 5, 11), kind=Absence.KIND_SICK)
        freeze_now(datetime(2026, 5, 11, 8, 0))
        _start(client, login_alice)
        assert _windows(app, login_alice) == []

    def test_holiday_blocks(self, client, login_alice, app, freeze_now):
        freeze_now(datetime(2026, 5, 1, 8, 0))  # Tag der Arbeit
        _start(client, login_alice)
        assert _windows(app, login_alice, date(2026, 5, 1)) == []

    def test_weekend_allowed(self, client, login_alice, app, freeze_now):
        freeze_now(datetime(2026, 5, 9, 10, 0))  # Sa
        _start(client, login_alice)
        assert _windows(app, login_alice, date(2026, 5, 9)) == [(time(10, 0), None)]

    def test_other_user_forbidden(self, client, login_alice, bob_id, freeze_now):
        freeze_now(datetime(2026, 5, 11, 8, 0))
        r = client.post(f"/user/{bob_id}/clock/start")
        assert r.status_code == 403


class TestClockEnd:
    def test_sets_rounded_end(self, client, login_alice, app, freeze_now):
        freeze_now(datetime(2026, 5, 11, 8, 0))
        _start(client, login_alice)
        freeze_now(datetime(2026, 5, 11, 16, 38))
        r = _end(client, login_alice)
        assert "Ende 16:45 gesetzt".encode() in r.data
        assert _windows(app, login_alice) == [(time(8, 0), time(16, 45))]

    def test_without_running_window(self, client, login_alice, app, freeze_now):
        freeze_now(datetime(2026, 5, 11, 16, 0))
        r = _end(client, login_alice)
        assert "läuft kein Zeitfenster".encode() in r.data

    def test_end_rounding_to_start_keeps_running(self, client, login_alice, app, freeze_now):
        freeze_now(datetime(2026, 5, 11, 8, 0))
        _start(client, login_alice)
        freeze_now(datetime(2026, 5, 11, 8, 5))
        r = _end(client, login_alice)
        assert "läuft weiter".encode() in r.data
        assert _windows(app, login_alice) == [(time(8, 0), None)]


class TestDashboardButtons:
    def test_today_shows_anfang_other_days_only_aendern(self, client, login_alice, freeze_now):
        freeze_now(datetime(2026, 5, 11, 8, 0))
        html = client.get(f"/user/{login_alice}?year=2026&month=5").data.decode()
        assert html.count(">Anfang</button>") == 1
        assert ">Ende</button>" not in html
        assert "Eintragen\n" not in html
        assert "Ändern" in html

    def test_running_window_shows_ende(self, client, login_alice, freeze_now, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(8, 0), None)
        freeze_now(datetime(2026, 5, 11, 9, 0))
        html = client.get(f"/user/{login_alice}?year=2026&month=5").data.decode()
        assert html.count(">Ende</button>") == 1
        assert ">Anfang</button>" not in html
        assert "btn-danger\" type=\"submit\">Ende" in html
        assert "läuft seit 08:00" in html

    def test_no_clock_button_on_holiday(self, client, login_alice, freeze_now):
        freeze_now(datetime(2026, 5, 1, 8, 0))
        html = client.get(f"/user/{login_alice}?year=2026&month=5").data.decode()
        assert ">Anfang</button>" not in html


class TestRunningWindowInSummary:
    def test_open_window_not_counted(self):
        user = type("U", (), {"daily_target": 8.0})()
        wds = [
            type("W", (), {"date": date(2026, 5, 11), "start_time": time(8, 0), "end_time": time(12, 0)})(),
            type("W", (), {"date": date(2026, 5, 11), "start_time": time(13, 0), "end_time": None})(),
        ]
        sm = logic.build_month_summary(user, 2026, 5, wds, [], today=date(2026, 5, 11))
        day = next(d for d in sm.days if d.date == date(2026, 5, 11))
        assert day.running
        assert day.net == 4.0
        assert day.end is None

    def test_edit_form_shows_open_window_with_empty_end(self, client, login_alice, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(8, 0), None)
        r = client.get(f"/user/{login_alice}/entry?date=2026-05-11")
        assert r.status_code == 200
