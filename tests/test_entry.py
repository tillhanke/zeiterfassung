"""Tests für den Einzel-Tageseintrag (entry_form + delete_day)."""
from __future__ import annotations

import re
from datetime import date, time

from models import Absence, WorkDay


def _post_entry(client, user_id, **overrides):
    payload = {
        "kind": "work",
        "date": "2026-05-11",
        "start_time": "09:00",
        "end_time": "17:30",
    }
    payload.update(overrides)
    return client.post(f"/user/{user_id}/entry", data=payload, follow_redirects=False)


def _minute_options(html):
    selects = re.findall(r'name="(?:start|end)_minute".*?</select>', html, re.S)
    return [re.findall(r'<option value="([^"]*)"', s) for s in selects]


def _selected_times(html):
    """Ausgewählte Zeiten je Zeile als (start, end)-Paare im Format HH:MM."""
    sel = {
        f: re.findall(rf'name="{f}".*?<option value="([^"]*)" selected', html, re.S)
        for f in ("start_hour", "start_minute", "end_hour", "end_minute")
    }
    return [
        (f"{sh}:{sm}", f"{eh}:{em}")
        for sh, sm, eh, em in zip(sel["start_hour"], sel["start_minute"], sel["end_hour"], sel["end_minute"])
    ]


class TestEntryFormGet:
    def test_get_form_renders(self, client, login_alice):
        r = client.get(f"/user/{login_alice}/entry")
        assert r.status_code == 200
        assert b"Tage w\xc3\xa4hlen" in r.data
        assert b'id="calendar"' in r.data
        assert b"Arbeit" in r.data
        assert b"Urlaub" in r.data
        assert b"Krank" in r.data

    def test_minute_select_offers_only_quarter_hours(self, client, login_alice):
        r = client.get(f"/user/{login_alice}/entry")
        assert _minute_options(r.data.decode()) == [["", "00", "15", "30", "45"]] * 2

    def test_hour_select_offers_full_day(self, client, login_alice):
        html = client.get(f"/user/{login_alice}/entry").data.decode()
        hours = re.findall(r'name="start_hour".*?</select>', html, re.S)[0]
        assert re.findall(r'<option value="([^"]*)"', hours) == [""] + [f"{h:02d}" for h in range(24)]

    def test_prefill_date_in_form(self, client, login_alice):
        r = client.get(f"/user/{login_alice}/entry?date=2026-05-11")
        assert r.status_code == 200
        assert b"2026-05-11" in r.data


class TestEntryWork:
    def test_creates_workday(self, client, login_alice, app):
        r = _post_entry(client, login_alice)
        assert r.status_code == 302
        with app.app_context():
            wd = WorkDay.query.filter_by(user_id=login_alice).one()
            assert wd.date == date(2026, 5, 11)
            assert wd.start_time == time(9, 0)
            assert wd.end_time == time(17, 30)

    def test_updates_existing_workday(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(8, 0), time(16, 0))
        _post_entry(client, login_alice, start_time="10:00", end_time="18:00")
        with app.app_context():
            wd = WorkDay.query.filter_by(user_id=login_alice).one()
            assert wd.start_time == time(10, 0)
            assert wd.end_time == time(18, 0)

    def test_work_overrides_existing_absence(self, client, login_alice, app, make_absence):
        make_absence(login_alice, date(2026, 5, 11), kind=Absence.KIND_VACATION)
        _post_entry(client, login_alice)
        with app.app_context():
            assert Absence.query.filter_by(user_id=login_alice).count() == 0
            assert WorkDay.query.filter_by(user_id=login_alice).count() == 1

    def test_invalid_date_format_stays_on_form(self, client, login_alice, app):
        r = client.post(
            f"/user/{login_alice}/entry",
            data={"kind": "work", "date": "kein-datum", "start_time": "09:00", "end_time": "17:00"},
        )
        assert r.status_code == 200
        assert b"Ung\xc3\xbcltiges Datum" in r.data
        with app.app_context():
            assert WorkDay.query.count() == 0

    def test_invalid_times_stay_on_form(self, client, login_alice, app):
        r = _post_entry(client, login_alice, start_time="nope", end_time="17:00")
        assert r.status_code == 200
        assert b"g\xc3\xbcltige Start" in r.data
        with app.app_context():
            assert WorkDay.query.count() == 0

    def test_end_before_start_rejected(self, client, login_alice, app):
        r = _post_entry(client, login_alice, start_time="17:00", end_time="09:00")
        assert r.status_code == 200
        assert b"nach Startzeit" in r.data
        with app.app_context():
            assert WorkDay.query.count() == 0

    def test_end_equal_start_rejected(self, client, login_alice, app):
        r = _post_entry(client, login_alice, start_time="09:00", end_time="09:00")
        assert r.status_code == 200
        with app.app_context():
            assert WorkDay.query.count() == 0


class TestEntryAbsence:
    def test_creates_vacation(self, client, login_alice, app):
        _post_entry(client, login_alice, kind="vacation")
        with app.app_context():
            a = Absence.query.filter_by(user_id=login_alice).one()
            assert a.kind == Absence.KIND_VACATION

    def test_creates_sick(self, client, login_alice, app):
        _post_entry(client, login_alice, kind="sick")
        with app.app_context():
            a = Absence.query.filter_by(user_id=login_alice).one()
            assert a.kind == Absence.KIND_SICK

    def test_vacation_overrides_existing_work(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 11))
        _post_entry(client, login_alice, kind="vacation")
        with app.app_context():
            assert WorkDay.query.filter_by(user_id=login_alice).count() == 0
            assert Absence.query.filter_by(user_id=login_alice).count() == 1

    def test_changes_absence_kind(self, client, login_alice, app, make_absence):
        make_absence(login_alice, date(2026, 5, 11), kind=Absence.KIND_VACATION)
        _post_entry(client, login_alice, kind="sick")
        with app.app_context():
            a = Absence.query.filter_by(user_id=login_alice).one()
            assert a.kind == Absence.KIND_SICK


class TestEntryUnknownKind:
    def test_returns_form_with_error(self, client, login_alice, app):
        r = _post_entry(client, login_alice, kind="bullshit")
        assert r.status_code == 200
        assert b"Unbekannter Eintragstyp" in r.data
        with app.app_context():
            assert WorkDay.query.count() == 0
            assert Absence.query.count() == 0


class TestDeleteDay:
    def test_delete_workday(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 11))
        r = client.post(f"/user/{login_alice}/day/2026-05-11/delete", follow_redirects=False)
        assert r.status_code == 302
        with app.app_context():
            assert WorkDay.query.count() == 0

    def test_delete_absence(self, client, login_alice, app, make_absence):
        make_absence(login_alice, date(2026, 5, 11))
        client.post(f"/user/{login_alice}/day/2026-05-11/delete")
        with app.app_context():
            assert Absence.query.count() == 0

    def test_delete_both(self, client, login_alice, app, make_workday, make_absence):
        # Edge case: theoretisch nicht möglich (Unique-Constraint, aber je separates
        # Datum). Wir simulieren das mit verschiedenen Daten und löschen den Workday-Tag.
        make_workday(login_alice, date(2026, 5, 11))
        make_absence(login_alice, date(2026, 5, 12))
        client.post(f"/user/{login_alice}/day/2026-05-11/delete")
        with app.app_context():
            assert WorkDay.query.count() == 0
            assert Absence.query.count() == 1  # 12.5. unangetastet

    def test_delete_with_invalid_date_format(self, client, login_alice):
        r = client.post(f"/user/{login_alice}/day/2026-13-99/delete")
        assert r.status_code == 400

    def test_delete_nonexistent_day_idempotent(self, client, login_alice):
        # Löschen eines nicht vorhandenen Eintrags ist erlaubt (kein Crash).
        r = client.post(f"/user/{login_alice}/day/2026-05-11/delete", follow_redirects=False)
        assert r.status_code == 302


def _post_windows(client, user_id, windows, **overrides):
    payload = {
        "kind": "work",
        "date": "2026-05-11",
        "start_time": [s for s, _ in windows],
        "end_time": [e for _, e in windows],
    }
    payload.update(overrides)
    return client.post(f"/user/{user_id}/entry", data=payload, follow_redirects=False)


def _windows(app, user_id):
    with app.app_context():
        return [
            (w.start_time, w.end_time)
            for w in WorkDay.query.filter_by(user_id=user_id).order_by(WorkDay.start_time)
        ]


class TestEntryMultipleWindows:
    def test_creates_two_windows(self, client, login_alice, app):
        r = _post_windows(client, login_alice, [("08:00", "12:00"), ("13:00", "17:00")])
        assert r.status_code == 302
        assert _windows(app, login_alice) == [
            (time(8, 0), time(12, 0)),
            (time(13, 0), time(17, 0)),
        ]

    def test_replaces_all_existing_windows(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(7, 0), time(9, 0))
        make_workday(login_alice, date(2026, 5, 11), time(10, 0), time(12, 0))
        _post_windows(client, login_alice, [("14:00", "18:00")])
        assert _windows(app, login_alice) == [(time(14, 0), time(18, 0))]

    def test_empty_rows_are_ignored(self, client, login_alice, app):
        _post_windows(client, login_alice, [("08:00", "12:00"), ("", "")])
        assert _windows(app, login_alice) == [(time(8, 0), time(12, 0))]

    def test_overlap_rejected_and_input_kept(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(9, 0), time(17, 0))
        r = _post_windows(client, login_alice, [("08:00", "12:00"), ("11:30", "17:00")])
        assert r.status_code == 200
        assert "überschneiden".encode() in r.data
        assert _selected_times(r.data.decode()) == [("08:00", "12:00"), ("11:30", "17:00")]
        # Bestehender Eintrag bleibt unverändert.
        assert _windows(app, login_alice) == [(time(9, 0), time(17, 0))]

    def test_one_invalid_window_rejects_all(self, client, login_alice, app):
        r = _post_windows(client, login_alice, [("08:00", "12:00"), ("15:00", "14:00")])
        assert r.status_code == 200
        assert _windows(app, login_alice) == []

    def test_get_prefills_existing_windows(self, client, login_alice, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(13, 15), time(17, 0))
        make_workday(login_alice, date(2026, 5, 11), time(7, 45), time(12, 0))
        r = client.get(f"/user/{login_alice}/entry?date=2026-05-11")
        assert _selected_times(r.data.decode()) == [("07:45", "12:00"), ("13:15", "17:00")]

    def test_off_grid_existing_time_is_kept(self, client, login_alice, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(8, 7), time(16, 0))
        r = client.get(f"/user/{login_alice}/entry?date=2026-05-11")
        assert _selected_times(r.data.decode()) == [("08:07", "16:00")]

    def test_get_without_entry_uses_default_window(self, client, login_alice):
        r = client.get(f"/user/{login_alice}/entry?date=2026-05-11")
        assert _selected_times(r.data.decode()) == [("09:00", "17:30")]

    def test_vacation_removes_all_windows(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(8, 0), time(12, 0))
        make_workday(login_alice, date(2026, 5, 11), time(13, 0), time(17, 0))
        _post_entry(client, login_alice, kind="vacation")
        assert _windows(app, login_alice) == []

    def test_delete_day_removes_all_windows(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(8, 0), time(12, 0))
        make_workday(login_alice, date(2026, 5, 11), time(13, 0), time(17, 0))
        client.post(f"/user/{login_alice}/day/2026-05-11/delete")
        assert _windows(app, login_alice) == []


class TestEntryHourMinuteSelects:
    def _post(self, client, user_id, **fields):
        data = {"kind": "work", "date": "2026-05-11"}
        data.update(fields)
        return client.post(f"/user/{user_id}/entry", data=data)

    def test_hour_and_minute_combined(self, client, login_alice, app):
        r = self._post(
            client, login_alice,
            start_hour=["08", "13"], start_minute=["15", "00"],
            end_hour=["12", "17"], end_minute=["00", "45"],
        )
        assert r.status_code == 302
        assert _windows(app, login_alice) == [
            (time(8, 15), time(12, 0)),
            (time(13, 0), time(17, 45)),
        ]

    def test_hour_without_minute_means_full_hour(self, client, login_alice, app):
        self._post(client, login_alice, start_hour="08", start_minute="", end_hour="12", end_minute="30")
        assert _windows(app, login_alice) == [(time(8, 0), time(12, 30))]

    def test_empty_row_ignored(self, client, login_alice, app):
        self._post(
            client, login_alice,
            start_hour=["08", ""], start_minute=["00", ""],
            end_hour=["12", ""], end_minute=["00", ""],
        )
        assert _windows(app, login_alice) == [(time(8, 0), time(12, 0))]

    def test_missing_end_hour_rejected(self, client, login_alice, app):
        r = self._post(client, login_alice, start_hour="08", start_minute="00", end_hour="", end_minute="30")
        assert r.status_code == 200
        assert _windows(app, login_alice) == []


class TestWeekend:
    def test_work_on_saturday_allowed(self, client, login_alice, app):
        r = _post_entry(client, login_alice, date="2026-05-09")
        assert r.status_code == 302
        assert _windows(app, login_alice) == [(time(9, 0), time(17, 30))]

    def test_vacation_on_weekend_rejected(self, client, login_alice, app):
        r = _post_entry(client, login_alice, date="2026-05-10", kind="vacation")
        assert r.status_code == 200
        assert b"nur an Werktagen" in r.data
        with app.app_context():
            assert Absence.query.count() == 0

    def test_sick_on_weekend_keeps_existing_work(self, client, login_alice, app, make_workday):
        make_workday(login_alice, date(2026, 5, 9), time(9, 0), time(12, 0))
        _post_entry(client, login_alice, date="2026-05-09", kind="sick")
        assert _windows(app, login_alice) == [(time(9, 0), time(12, 0))]


class TestUnifiedForm:
    """Ein Formular für einen oder mehrere Tage (ERF-9, ERF-16)."""

    def test_holidays_and_minute_grid_in_form(self, client, login_alice):
        html = client.get(f"/user/{login_alice}/entry?date=2026-05-11").data.decode()
        assert '"2026-05-01": "Tag der Arbeit"' in html
        assert _minute_options(html) == [["", "00", "15", "30", "45"]] * 2

    def test_today_preselected_without_date(self, client, login_alice):
        html = client.get(f"/user/{login_alice}/entry").data.decode()
        assert f'id="datesField" value="{date.today().isoformat()}"' in html
        assert "Eintragen</h1>" in html

    def test_several_days_via_entry_route(self, client, login_alice, app):
        """ERF-9: mehrere Tage über das gemeinsame Formular."""
        r = client.post(
            f"/user/{login_alice}/entry",
            data={"kind": "work", "dates": "2026-05-11,2026-05-13",
                  "start_time": "08:00", "end_time": "16:00"},
        )
        assert r.status_code == 302
        with app.app_context():
            assert sorted(w.date for w in WorkDay.query.all()) == [date(2026, 5, 11), date(2026, 5, 13)]
        page = client.get(r.headers["Location"]).data.decode()
        assert "Arbeitszeit für 2 Tage gespeichert." in page

    def test_single_day_message_names_date(self, client, login_alice):
        r = _post_entry(client, login_alice)
        page = client.get(r.headers["Location"]).data.decode()
        assert "Arbeitszeit für 11.05.2026 gespeichert." in page

    def test_single_weekend_absence_rejected(self, client, login_alice, app):
        """ERF-7: ein einzelner Wochenendtag mit Urlaub wird abgelehnt."""
        r = _post_entry(client, login_alice, kind="vacation", date="2026-05-09")
        assert r.status_code == 200
        assert "nur an Werktagen".encode() in r.data
        with app.app_context():
            assert Absence.query.count() == 0

    def test_edit_existing_absence_prefills_kind(self, client, login_alice, make_absence):
        make_absence(login_alice, date(2026, 5, 11), Absence.KIND_SICK)
        html = client.get(f"/user/{login_alice}/entry?date=2026-05-11").data.decode()
        assert "Eintrag ändern</h1>" in html
        assert 'id="kindSick" value="sick" checked' in html
        assert '"2026-05-11": "sick"' in html  # Kalender markiert vorhandenen Eintrag

    def test_error_keeps_selection(self, client, login_alice):
        r = client.post(
            f"/user/{login_alice}/entry",
            data={"kind": "work", "dates": "2026-05-11,2026-05-12",
                  "start_time": "17:00", "end_time": "08:00"},
        )
        assert r.status_code == 200
        assert b'id="datesField" value="2026-05-11,2026-05-12"' in r.data
        assert _selected_times(r.data.decode()) == [("17:00", "08:00")]

    def test_last_workday_preset(self, client, login_alice, make_workday):
        """ERF-16: Vorlage „Wie letzter Arbeitstag“ mit dessen Zeitfenstern."""
        make_workday(login_alice, date(2026, 5, 7), time(9, 0), time(12, 0))
        make_workday(login_alice, date(2026, 5, 8), time(8, 0), time(12, 0))
        make_workday(login_alice, date(2026, 5, 8), time(12, 30), time(16, 45))
        html = client.get(f"/user/{login_alice}/entry").data.decode()
        assert "Wie letzter Arbeitstag" in html
        assert "Fr 08.05.:" in html
        assert '[["08:00", "12:00"], ["12:30", "16:45"]]' in html

    def test_no_preset_without_history(self, client, login_alice):
        html = client.get(f"/user/{login_alice}/entry").data.decode()
        assert "Wie letzter Arbeitstag" not in html
