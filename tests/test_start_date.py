"""Tests für Startdatum und Übertrag (Saldo zum Stichtag)."""
from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace

from sqlalchemy import text

import logic
from models import Absence, User, WorkDay, db


def _user(start_date=None, start_balance=0.0):
    return SimpleNamespace(
        weekly_hours=40.0, daily_target=8.0, start_date=start_date, start_balance=start_balance
    )


def _wd(d, start=time(9, 0), end=time(17, 30)):
    return SimpleNamespace(date=d, start_time=start, end_time=end)


TODAY = date(2026, 5, 31)


class TestMonthSummary:
    def test_days_before_start_are_inactive_and_not_counted(self):
        # Mi 13.5.2026 als Start; Eintrag am Mo 11.5. zählt nicht.
        u = _user(date(2026, 5, 13), 0.0)
        sm = logic.build_month_summary(
            u, 2026, 5, [_wd(date(2026, 5, 11))], [], today=TODAY
        )
        by_date = {d.date: d for d in sm.days}
        assert by_date[date(2026, 5, 11)].kind == "inactive"
        assert "Eintrag zählt nicht" in by_date[date(2026, 5, 11)].note
        assert by_date[date(2026, 5, 12)].kind == "inactive"
        assert by_date[date(2026, 5, 13)].kind == "empty"
        # Ohne Startdatum: Mai bis 31.5. = 19 Werktage ohne Feiertage
        # (1.5., 14.5., 25.5. fallen weg). Ab 13.5.: 13., 15., 18.-22., 26.-29. = 11.
        assert sm.target_hours == 11 * 8.0
        assert sm.actual_hours == 0.0

    def test_opening_balance_added_to_saldo_in_start_month(self):
        u = _user(date(2026, 5, 13), 12.5)
        sm = logic.build_month_summary(u, 2026, 5, [], [], today=date(2026, 5, 13))
        assert sm.opening_balance == 12.5
        assert sm.saldo == 12.5 - 8.0  # Übertrag minus leerer Starttag
        start_day = next(d for d in sm.days if d.date == date(2026, 5, 13))
        assert start_day.note.startswith("Übertrag +12:30 h")

    def test_negative_opening_balance(self):
        u = _user(date(2026, 5, 13), -4.0)
        sm = logic.build_month_summary(
            u, 2026, 5, [_wd(date(2026, 5, 13), time(8, 0), time(16, 30))], [],
            today=date(2026, 5, 13),
        )
        assert sm.saldo == -4.0  # 8h gearbeitet bei 8h Soll

    def test_opening_balance_only_in_start_month(self):
        u = _user(date(2026, 5, 13), 12.5)
        sm = logic.build_month_summary(u, 2026, 6, [], [], today=date(2026, 5, 31))
        assert sm.opening_balance == 0.0

    def test_month_entirely_before_start(self):
        u = _user(date(2026, 5, 13), 3.0)
        sm = logic.build_month_summary(
            u, 2026, 4, [_wd(date(2026, 4, 14))], [], today=TODAY
        )
        assert all(d.kind == "inactive" for d in sm.days)
        assert sm.saldo == 0.0

    def test_absence_before_start_is_inactive(self):
        u = _user(date(2026, 5, 13))
        absence = SimpleNamespace(date=date(2026, 5, 12), kind=Absence.KIND_VACATION)
        sm = logic.build_month_summary(u, 2026, 5, [], [absence], today=TODAY)
        assert sm.vacation_days == 0
        assert next(d for d in sm.days if d.date == date(2026, 5, 12)).kind == "inactive"


class TestYearSummary:
    def test_year_counts_from_start_and_includes_balance(self):
        u = _user(date(2026, 5, 13), 12.5)
        ys = logic.build_year_summary(
            u, 2026, [_wd(date(2026, 3, 2))], [], today=date(2026, 5, 13)
        )
        assert ys.worked_days == 0  # Eintrag im März liegt vor dem Start
        assert ys.target_hours == 8.0  # nur 13.5.
        assert ys.saldo == 12.5 - 8.0

    def test_year_saldo_equals_sum_of_month_saldos(self):
        u = _user(date(2026, 5, 13), -3.0)
        wds = [_wd(date(2026, 5, 20)), _wd(date(2026, 6, 3))]
        ys = logic.build_year_summary(u, 2026, wds, [], today=date(2026, 6, 30))
        months = sum(
            logic.build_month_summary(u, 2026, m, wds, [], today=date(2026, 6, 30)).saldo
            for m in range(1, 13)
        )
        assert abs(ys.saldo - months) < 1e-9

    def test_later_year_has_no_balance(self):
        u = _user(date(2026, 5, 13), 12.5)
        ys = logic.build_year_summary(u, 2027, [], [], today=date(2027, 1, 4))
        assert ys.opening_balance == 0.0


class TestAdmin:
    def test_create_with_start_and_balance(self, client, login_admin, app):
        client.post(
            "/admin/users",
            data={"name": "Neu", "weekly_hours": "40", "start_date": "2026-05-13",
                  "start_balance": "-7,5"},
        )
        with app.app_context():
            u = User.query.filter_by(name="Neu").one()
            assert u.start_date == date(2026, 5, 13)
            assert u.start_balance == -7.5

    def test_create_without_start(self, client, login_admin, app):
        client.post("/admin/users", data={"name": "Neu", "weekly_hours": "40"})
        with app.app_context():
            u = User.query.filter_by(name="Neu").one()
            assert u.start_date is None
            assert u.start_balance == 0.0

    def test_balance_without_date_rejected(self, client, login_admin, app):
        client.post(
            "/admin/users",
            data={"name": "Neu", "weekly_hours": "40", "start_balance": "5"},
        )
        with app.app_context():
            assert User.query.count() == 0

    def test_invalid_balance_rejected(self, client, login_admin, app):
        client.post(
            "/admin/users",
            data={"name": "Neu", "weekly_hours": "40", "start_date": "2026-05-13",
                  "start_balance": "viel"},
        )
        with app.app_context():
            assert User.query.count() == 0

    def test_update_start_and_clear(self, client, login_admin, app, alice_id):
        client.post(
            f"/admin/users/{alice_id}",
            data={"action": "start", "start_date": "2026-05-13", "start_balance": "4"},
        )
        with app.app_context():
            u = db.session.get(User, alice_id)
            assert (u.start_date, u.start_balance) == (date(2026, 5, 13), 4.0)
        client.post(
            f"/admin/users/{alice_id}",
            data={"action": "start", "start_date": "", "start_balance": ""},
        )
        with app.app_context():
            u = db.session.get(User, alice_id)
            assert (u.start_date, u.start_balance) == (None, 0.0)

    def test_weekly_hours_update_keeps_start(self, client, login_admin, app, alice_id):
        client.post(
            f"/admin/users/{alice_id}",
            data={"action": "start", "start_date": "2026-05-13", "start_balance": "4"},
        )
        client.post(f"/admin/users/{alice_id}", data={"weekly_hours": "30"})
        with app.app_context():
            u = db.session.get(User, alice_id)
            assert (u.start_date, u.start_balance, u.weekly_hours) == (
                date(2026, 5, 13), 4.0, 30.0,
            )


def _set_start(app, user_id, start, balance=0.0):
    with app.app_context():
        u = db.session.get(User, user_id)
        u.start_date, u.start_balance = start, balance
        db.session.commit()


class TestEntriesBeforeStart:
    def test_entry_before_start_rejected(self, client, app, login_alice):
        _set_start(app, login_alice, date(2026, 5, 13))
        client.post(
            f"/user/{login_alice}/entry",
            data={"kind": "work", "date": "2026-05-12", "start_time": "09:00", "end_time": "17:00"},
        )
        with app.app_context():
            assert WorkDay.query.count() == 0

    def test_entry_on_start_date_allowed(self, client, app, login_alice):
        _set_start(app, login_alice, date(2026, 5, 13))
        client.post(
            f"/user/{login_alice}/entry",
            data={"kind": "work", "date": "2026-05-13", "start_time": "09:00", "end_time": "17:00"},
        )
        with app.app_context():
            assert WorkDay.query.count() == 1

    def test_bulk_skips_days_before_start(self, client, app, login_alice):
        _set_start(app, login_alice, date(2026, 5, 13))
        client.post(
            f"/user/{login_alice}/bulk-entry",
            data={"kind": "work", "dates": "2026-05-11,2026-05-12,2026-05-13",
                  "start_time": "09:00", "end_time": "17:00"},
        )
        with app.app_context():
            assert [w.date for w in WorkDay.query.all()] == [date(2026, 5, 13)]

    def test_clock_start_before_start_rejected(self, client, app, login_alice):
        _set_start(app, login_alice, date(2099, 1, 1))
        client.post(f"/user/{login_alice}/clock/start")
        with app.app_context():
            assert WorkDay.query.count() == 0

    def test_existing_entries_are_kept(self, client, app, login_alice, make_workday):
        make_workday(login_alice, date(2026, 5, 11))
        _set_start(app, login_alice, date(2026, 5, 13), 2.0)
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        assert r.status_code == 200
        assert "Eintrag zählt nicht".encode() in r.data
        assert "Übertrag +2:00 h".encode() in r.data
        with app.app_context():
            assert WorkDay.query.count() == 1


class TestMigrateUsers:
    def test_old_users_table_gets_columns(self, app, runner):
        with app.app_context():
            db.session.execute(text("DROP TABLE users"))
            db.session.execute(
                text(
                    "CREATE TABLE users (id INTEGER NOT NULL, name VARCHAR(120) NOT NULL, "
                    "weekly_hours FLOAT NOT NULL, active BOOLEAN NOT NULL, "
                    "PRIMARY KEY (id), UNIQUE (name))"
                )
            )
            db.session.execute(
                text("INSERT INTO users (id, name, weekly_hours, active) VALUES (1, 'Alt', 40, 1)")
            )
            db.session.commit()

        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0

        with app.app_context():
            u = db.session.get(User, 1)
            assert (u.name, u.start_date, u.start_balance) == ("Alt", None, 0.0)

        # Zweiter Lauf ist ein No-op.
        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0
