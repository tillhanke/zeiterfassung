"""Tests für Gesamtsaldo und die Einstellung "Saldo zum Jahreswechsel nullen"."""
from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace

import logic
from app import running_total, year_summary_for, yearly_reset_enabled
from models import Setting, User, db


def _user(start_date=None, start_balance=0.0):
    return SimpleNamespace(
        weekly_hours=40.0, daily_target=8.0, start_date=start_date, start_balance=start_balance
    )


def _wd(d, start=time(9, 0), end=time(17, 30)):
    return SimpleNamespace(date=d, start_time=start, end_time=end)


class TestCarryOverLogic:
    def test_no_start_no_entries_is_zero(self):
        assert logic.carry_over_into(_user(), 2026, [], [], today=date(2026, 3, 1)) == 0.0

    def test_sums_previous_years_from_start(self):
        u = _user(date(2024, 11, 4), 10.0)
        wds = [_wd(date(2024, 11, 4)), _wd(date(2025, 6, 2)), _wd(date(2026, 1, 5))]
        today = date(2026, 3, 1)
        expected = sum(
            logic.build_year_summary(
                u, y, [w for w in wds if w.date.year == y], [], today=today
            ).saldo
            for y in (2024, 2025)
        )
        assert logic.carry_over_into(u, 2026, wds, [], today=today) == expected

    def test_without_start_counts_from_year_of_first_entry(self):
        u = _user()
        wds = [_wd(date(2025, 3, 3))]
        today = date(2026, 3, 1)
        expected = logic.build_year_summary(u, 2025, wds, [], today=today).saldo
        assert logic.carry_over_into(u, 2026, wds, [], today=today) == expected

    def test_start_in_target_year_has_no_carry(self):
        u = _user(date(2026, 2, 2), 10.0)
        assert logic.carry_over_into(u, 2026, [], [], today=date(2026, 3, 1)) == 0.0

    def test_carry_counts_into_year_saldo(self):
        ys = logic.build_year_summary(
            _user(), 2026, [], [], today=date(2025, 12, 31), carry_over=7.5
        )
        assert ys.saldo == 7.5


class TestSetting:
    def test_default_is_reset(self, app):
        with app.app_context():
            assert yearly_reset_enabled() is True

    def test_toggle_off_and_on(self, client, login_admin, app):
        client.post("/admin/settings", data={})
        with app.app_context():
            assert yearly_reset_enabled() is False
        client.post("/admin/settings", data={"yearly_reset": "1"})
        with app.app_context():
            assert yearly_reset_enabled() is True

    def test_requires_admin(self, client, login_alice, app):
        client.post("/admin/settings", data={})
        with app.app_context():
            assert yearly_reset_enabled() is True

    def test_settings_page_shows_toggle(self, client, login_admin):
        """NUTZ-8: Firmeneinstellungen auf eigener Seite."""
        r = client.get("/admin/settings")
        assert "Saldo zum Jahreswechsel auf 0 setzen".encode() in r.data
        assert b'id="yearly_reset"' in r.data
        assert b"checked" in r.data


def _prepare(app, alice_id):
    """Alice startet am 1.12. des Vorjahres mit +5 h."""
    last_year = date.today().year - 1
    with app.app_context():
        u = db.session.get(User, alice_id)
        u.start_date, u.start_balance = date(last_year, 12, 1), 5.0
        db.session.commit()
    return last_year


class TestRunningTotal:
    def test_with_reset_only_current_year(self, app, alice_id):
        _prepare(app, alice_id)
        with app.app_context():
            u = db.session.get(User, alice_id)
            total, since = running_total(u)
            assert since == date(date.today().year, 1, 1)
            assert total == year_summary_for(u, date.today().year).saldo
            assert year_summary_for(u, date.today().year).carry_over == 0.0

    def test_without_reset_includes_previous_years(self, app, alice_id, make_workday):
        last_year = _prepare(app, alice_id)
        make_workday(alice_id, date(last_year, 12, 1))
        with app.app_context():
            u = db.session.get(User, alice_id)
            with_reset, _ = running_total(u)
            last_year_saldo = year_summary_for(u, last_year).saldo
            Setting.set_bool(Setting.YEARLY_RESET, False)
            db.session.commit()
            total, since = running_total(u)
            assert since == date(last_year, 12, 1)
            assert abs(total - (with_reset + last_year_saldo)) < 1e-9
            assert year_summary_for(u, date.today().year).carry_over == last_year_saldo

    def test_without_reset_and_start_since_first_entry_year(self, app, alice_id, make_workday):
        first_year = date.today().year - 2
        make_workday(alice_id, date(first_year, 6, 1))
        with app.app_context():
            Setting.set_bool(Setting.YEARLY_RESET, False)
            db.session.commit()
            _, since = running_total(db.session.get(User, alice_id))
            assert since == date(first_year, 1, 1)

    def test_dashboard_shows_running_total(self, client, login_alice):
        r = client.get(f"/user/{login_alice}")
        assert r.status_code == 200
        assert b"Aktueller Gesamtsaldo" in r.data

    def test_admin_shows_running_total(self, client, login_admin, alice_id):
        r = client.get("/admin")
        assert b"Gesamtsaldo" in r.data
