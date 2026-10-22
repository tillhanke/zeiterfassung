"""Tests für den Sammeleintrag mehrerer Tage (bulk_entry_form)."""
from __future__ import annotations

from datetime import date, time

from models import Absence, WorkDay


def _bulk_post(client, user_id, dates, kind="work", start="09:00", end="17:30", **extra):
    data = {"kind": kind, "dates": dates, "start_time": start, "end_time": end}
    data.update(extra)
    return client.post(f"/user/{user_id}/bulk-entry", data=data, follow_redirects=False)


def _minute_options(html):
    import re

    selects = re.findall(r'name="(?:start|end)_minute".*?</select>', html, re.S)
    return [re.findall(r'<option value="([^"]*)"', s) for s in selects]


class TestBulkGet:
    def test_get_redirects_to_entry_form(self, client, login_alice):
        """Sammeleintrag ist Teil des Eintragsformulars (ERF-9)."""
        r = client.get(f"/user/{login_alice}/bulk-entry")
        assert r.status_code == 302
        assert r.headers["Location"].endswith(f"/user/{login_alice}/entry")

class TestBulkWork:
    def test_three_non_consecutive_workdays(self, client, login_alice, app):
        r = _bulk_post(client, login_alice, "2026-05-12, 2026-05-15, 2026-05-22")
        assert r.status_code == 302
        with app.app_context():
            wds = WorkDay.query.filter_by(user_id=login_alice).order_by(WorkDay.date).all()
            assert [w.date for w in wds] == [
                date(2026, 5, 12),
                date(2026, 5, 15),
                date(2026, 5, 22),
            ]
            for w in wds:
                assert w.start_time == time(9, 0)
                assert w.end_time == time(17, 30)

    def test_redirect_to_first_date_month(self, client, login_alice):
        r = _bulk_post(client, login_alice, "2026-07-15, 2026-05-12")
        assert r.status_code == 302
        # Erstes Datum (sortiert) ist im Mai
        assert "year=2026" in r.headers["Location"]
        assert "month=5" in r.headers["Location"]

    def test_overwrites_existing_workday(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 12), time(8, 0), time(16, 0))
        _bulk_post(client, login_alice, "2026-05-12", start="10:00", end="18:00")
        with app.app_context():
            wd = WorkDay.query.one()
            assert wd.start_time == time(10, 0)
            assert wd.end_time == time(18, 0)

    def test_overrides_existing_absence(self, client, login_alice, app, make_absence):
        make_absence(login_alice, date(2026, 5, 12), kind=Absence.KIND_VACATION)
        _bulk_post(client, login_alice, "2026-05-12")
        with app.app_context():
            assert Absence.query.count() == 0
            assert WorkDay.query.count() == 1

    def test_dedup_duplicates(self, client, login_alice, app):
        _bulk_post(client, login_alice, "2026-05-12, 2026-05-12, 2026-05-12")
        with app.app_context():
            assert WorkDay.query.count() == 1

    def test_various_separators(self, client, login_alice, app):
        # Komma, Whitespace, Newline, Semikolon
        dates = "2026-05-12,2026-05-13 2026-05-14;2026-05-15\n2026-05-18"
        _bulk_post(client, login_alice, dates)
        with app.app_context():
            assert WorkDay.query.count() == 5


class TestBulkMultipleWindows:
    def test_two_windows_on_each_day(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 12), time(6, 0), time(7, 0))
        r = client.post(
            f"/user/{login_alice}/bulk-entry",
            data={
                "kind": "work",
                "dates": "2026-05-12, 2026-05-13",
                "start_time": ["13:00", "08:00"],
                "end_time": ["17:00", "12:00"],
            },
        )
        assert r.status_code == 302
        with app.app_context():
            for d in (date(2026, 5, 12), date(2026, 5, 13)):
                wds = WorkDay.query.filter_by(date=d).order_by(WorkDay.start_time).all()
                assert [(w.start_time, w.end_time) for w in wds] == [
                    (time(8, 0), time(12, 0)),
                    (time(13, 0), time(17, 0)),
                ]

    def test_overlap_rejected(self, client, login_alice, app):
        r = client.post(
            f"/user/{login_alice}/bulk-entry",
            data={
                "kind": "work",
                "dates": "2026-05-12",
                "start_time": ["08:00", "10:00"],
                "end_time": ["12:00", "14:00"],
            },
        )
        assert r.status_code == 200
        assert "überschneiden".encode() in r.data
        with app.app_context():
            assert WorkDay.query.count() == 0


class TestBulkAbsence:
    def test_vacation_multiple_days(self, client, login_alice, app):
        _bulk_post(client, login_alice, "2026-05-12, 2026-05-13, 2026-05-14", kind="vacation")
        with app.app_context():
            absences = Absence.query.all()
            assert len(absences) == 3
            for a in absences:
                assert a.kind == Absence.KIND_VACATION

    def test_sick_multiple_days(self, client, login_alice, app):
        _bulk_post(client, login_alice, "2026-05-12, 2026-05-13", kind="sick")
        with app.app_context():
            assert Absence.query.filter_by(kind=Absence.KIND_SICK).count() == 2

    def test_vacation_overrides_workday(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 12))
        _bulk_post(client, login_alice, "2026-05-12", kind="vacation")
        with app.app_context():
            assert WorkDay.query.count() == 0
            assert Absence.query.count() == 1

    def test_changes_absence_kind(self, client, login_alice, app, make_absence):
        make_absence(login_alice, date(2026, 5, 12), kind=Absence.KIND_VACATION)
        _bulk_post(client, login_alice, "2026-05-12", kind="sick")
        with app.app_context():
            a = Absence.query.one()
            assert a.kind == Absence.KIND_SICK


class TestBulkWeekend:
    def test_work_on_weekend_saved(self, client, login_alice, app):
        _bulk_post(client, login_alice, "2026-05-08, 2026-05-09, 2026-05-10")
        with app.app_context():
            assert WorkDay.query.count() == 3

    def test_vacation_skips_weekend_days(self, client, login_alice, app):
        r = _bulk_post(client, login_alice, "2026-05-08, 2026-05-09, 2026-05-10, 2026-05-11", kind="vacation")
        assert r.status_code == 302
        with app.app_context():
            assert sorted(a.date for a in Absence.query.all()) == [date(2026, 5, 8), date(2026, 5, 11)]
        page = client.get(r.headers["Location"]).data.decode()
        assert "2 Wochenendtage übersprungen" in page

    def test_vacation_only_weekend_rejected(self, client, login_alice, app):
        r = _bulk_post(client, login_alice, "2026-05-09, 2026-05-10", kind="vacation")
        assert r.status_code == 200
        assert "nur an Werktagen".encode() in r.data
        with app.app_context():
            assert Absence.query.count() == 0


class TestBulkValidation:
    def test_invalid_date_in_list_stays_on_form(self, client, login_alice, app):
        r = _bulk_post(client, login_alice, "2026-05-12, kein-datum")
        assert r.status_code == 200
        assert b"Ung\xc3\xbcltiges Datum" in r.data
        with app.app_context():
            assert WorkDay.query.count() == 0  # Atomic: bei Fehler keine Einträge

    def test_empty_dates_rejected(self, client, login_alice, app):
        r = _bulk_post(client, login_alice, "")
        assert r.status_code == 200
        assert b"mindestens ein Datum" in r.data
        with app.app_context():
            assert WorkDay.query.count() == 0

    def test_only_separators_rejected(self, client, login_alice, app):
        r = _bulk_post(client, login_alice, "   , ;\n,, ")
        assert r.status_code == 200
        assert b"mindestens ein Datum" in r.data

    def test_invalid_time_format_rejected(self, client, login_alice, app):
        r = _bulk_post(client, login_alice, "2026-05-12", start="nope", end="17:00")
        assert r.status_code == 200
        assert b"g\xc3\xbcltige Start" in r.data
        with app.app_context():
            assert WorkDay.query.count() == 0

    def test_end_before_start_rejected(self, client, login_alice, app):
        r = _bulk_post(client, login_alice, "2026-05-12", start="17:00", end="09:00")
        assert r.status_code == 200
        assert b"nach Startzeit" in r.data
        with app.app_context():
            assert WorkDay.query.count() == 0

    def test_unknown_kind_rejected(self, client, login_alice, app):
        r = _bulk_post(client, login_alice, "2026-05-12", kind="invalid")
        assert r.status_code == 200
        assert b"Unbekannter Eintragstyp" in r.data
        with app.app_context():
            assert WorkDay.query.count() == 0
            assert Absence.query.count() == 0

    def test_absence_does_not_require_times(self, client, login_alice, app):
        # Für Urlaub/Krank dürfen start/end fehlen.
        r = client.post(
            f"/user/{login_alice}/bulk-entry",
            data={"kind": "vacation", "dates": "2026-05-12"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        with app.app_context():
            assert Absence.query.count() == 1


class TestBulkAtomicity:
    """Beim Fehler darf KEIN Tag aus der Liste geschrieben werden."""

    def test_no_partial_writes_on_invalid_date(self, client, login_alice, app):
        _bulk_post(client, login_alice, "2026-05-12, 2026-05-13, kaputt")
        with app.app_context():
            assert WorkDay.query.count() == 0
            assert Absence.query.count() == 0

    def test_no_partial_writes_on_bad_times(self, client, login_alice, app):
        _bulk_post(client, login_alice, "2026-05-12, 2026-05-13", start="x", end="y")
        with app.app_context():
            assert WorkDay.query.count() == 0
