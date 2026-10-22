"""Tests für das Admin-Panel und User-Verwaltung."""
from __future__ import annotations

from datetime import date, time, timedelta

import logic
from models import User, db


class TestAdminPanel:
    def test_panel_renders(self, client, login_admin, alice_id, bob_id):
        r = client.get("/admin")
        assert r.status_code == 200
        assert "Übersicht</h1>".encode() in r.data
        assert b"Alice" in r.data
        assert b"Bob" in r.data

    def test_panel_includes_inactive(self, client, login_admin, alice_id, inactive_user_id):
        r = client.get("/admin")
        # Admin-Liste zeigt ALLE Nutzer (auch inaktive) -- siehe app.py admin route.
        assert b"Alice" in r.data
        assert b"Inaktiv" in r.data
        assert b"inaktiv" in r.data  # Status-Badge


class TestCreateUser:
    def test_create_valid(self, client, login_admin, app):
        r = client.post(
            "/admin/users",
            data={"name": "Neu", "weekly_hours": "30"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        with app.app_context():
            u = User.query.filter_by(name="Neu").one()
            assert u.weekly_hours == 30.0
            assert u.active is True

    def test_create_with_comma_decimal(self, client, login_admin, app):
        # Deutsche Komma-Dezimalschreibweise wird unterstützt.
        client.post("/admin/users", data={"name": "X", "weekly_hours": "32,5"})
        with app.app_context():
            assert User.query.filter_by(name="X").one().weekly_hours == 32.5

    def test_empty_name_rejected(self, client, login_admin, app):
        client.post("/admin/users", data={"name": "  ", "weekly_hours": "40"})
        with app.app_context():
            assert User.query.count() == 0

    def test_duplicate_name_rejected(self, client, login_admin, app, alice_id):
        client.post("/admin/users", data={"name": "Alice", "weekly_hours": "40"})
        with app.app_context():
            assert User.query.filter_by(name="Alice").count() == 1

    def test_invalid_hours_format_rejected(self, client, login_admin, app):
        client.post("/admin/users", data={"name": "Neu", "weekly_hours": "abc"})
        with app.app_context():
            assert User.query.filter_by(name="Neu").count() == 0

    def test_zero_hours_rejected(self, client, login_admin, app):
        client.post("/admin/users", data={"name": "Neu", "weekly_hours": "0"})
        with app.app_context():
            assert User.query.count() == 0

    def test_negative_hours_rejected(self, client, login_admin, app):
        client.post("/admin/users", data={"name": "Neu", "weekly_hours": "-5"})
        with app.app_context():
            assert User.query.count() == 0

    def test_too_high_hours_rejected(self, client, login_admin, app):
        client.post("/admin/users", data={"name": "Neu", "weekly_hours": "70"})
        with app.app_context():
            assert User.query.count() == 0

    def test_max_allowed_hours_60(self, client, login_admin, app):
        client.post("/admin/users", data={"name": "Max", "weekly_hours": "60"})
        with app.app_context():
            assert User.query.filter_by(name="Max").one().weekly_hours == 60.0


class TestUpdateUser:
    def test_update_weekly_hours(self, client, login_admin, app, alice_id):
        client.post(f"/admin/users/{alice_id}", data={"weekly_hours": "35"})
        with app.app_context():
            assert User.query.get(alice_id).weekly_hours == 35.0

    def test_invalid_hours_keeps_old_value(self, client, login_admin, app, alice_id):
        client.post(f"/admin/users/{alice_id}", data={"weekly_hours": "100"})
        with app.app_context():
            assert User.query.get(alice_id).weekly_hours == 40.0  # unverändert

    def test_invalid_hours_format_keeps_old_value(self, client, login_admin, app, alice_id):
        client.post(f"/admin/users/{alice_id}", data={"weekly_hours": "garbage"})
        with app.app_context():
            assert User.query.get(alice_id).weekly_hours == 40.0

    def test_deactivate(self, client, login_admin, app, alice_id):
        client.post(f"/admin/users/{alice_id}", data={"action": "deactivate"})
        with app.app_context():
            assert User.query.get(alice_id).active is False

    def test_activate(self, client, login_admin, app, inactive_user_id):
        client.post(f"/admin/users/{inactive_user_id}", data={"action": "activate"})
        with app.app_context():
            assert User.query.get(inactive_user_id).active is True

    def test_update_nonexistent_user_404(self, client, login_admin):
        r = client.post("/admin/users/99999", data={"weekly_hours": "40"})
        assert r.status_code == 404

    def test_inactive_user_filtered_from_topbar(self, client, alice_id, inactive_user_id):
        # Inaktive Nutzerinnen tauchen NICHT in der Topbar auf.
        r = client.get("/")
        assert b"Alice" in r.data
        assert b"Inaktiv" not in r.data


class TestUserDetail:
    """Detailseite einer Nutzerin: Stammdaten in einem Formular (NUTZ-5)."""

    def _save(self, client, user_id, **fields):
        data = {"action": "save", "name": "Alice", "weekly_hours": "40",
                "start_date": "", "start_balance": ""}
        data.update(fields)
        return client.post(f"/admin/users/{user_id}", data=data)

    def test_detail_shows_formatted_values(self, client, login_admin, app, alice_id):
        with app.app_context():
            u = db.session.get(User, alice_id)
            u.weekly_hours, u.start_date, u.start_balance = 38.5, date(2026, 5, 1), 6.5
            db.session.commit()
        html = client.get(f"/admin/users/{alice_id}").data.decode()
        assert 'value="38,5"' in html
        assert 'value="2026-05-01"' in html
        assert 'value="+6:30"' in html
        assert "Einträge ansehen / korrigieren" in html

    def test_save_all_fields_at_once(self, client, login_admin, app, alice_id):
        """NUTZ-5: Name, Wochenstunden, Startdatum und Übertrag zusammen speichern."""
        r = self._save(client, alice_id, name="Alicia", weekly_hours="32,5",
                       start_date="2026-05-04", start_balance="−2:30")
        assert r.status_code == 302
        assert r.headers["Location"].endswith(f"/admin/users/{alice_id}")
        with app.app_context():
            u = db.session.get(User, alice_id)
            assert (u.name, u.weekly_hours, u.start_date, u.start_balance) == (
                "Alicia", 32.5, date(2026, 5, 4), -2.5)

    def test_rename_to_existing_name_rejected(self, client, login_admin, app, alice_id, bob_id):
        """NUTZ-4: Namen bleiben eindeutig, auch beim Umbenennen."""
        r = self._save(client, alice_id, name="Bob", weekly_hours="20")
        assert r.status_code == 400
        assert "existiert bereits".encode() in r.data
        assert b'value="20"' in r.data  # Eingaben bleiben erhalten
        with app.app_context():
            u = db.session.get(User, alice_id)
            assert (u.name, u.weekly_hours) == ("Alice", 40.0)

    def test_invalid_input_changes_nothing(self, client, login_admin, app, alice_id):
        r = self._save(client, alice_id, name="Neu", weekly_hours="abc")
        assert r.status_code == 400
        with app.app_context():
            assert db.session.get(User, alice_id).name == "Alice"

    def test_deactivate_from_detail(self, client, login_admin, app, alice_id):
        """NUTZ-6: Deaktivieren auf der Detailseite, Daten bleiben."""
        r = client.post(f"/admin/users/{alice_id}", data={"action": "deactivate"},
                        follow_redirects=True)
        assert "deaktiviert. Ihre Daten bleiben erhalten".encode() in r.data
        assert b"Wieder aktivieren" in r.data

    def test_detail_requires_admin(self, client, login_alice):
        r = client.get(f"/admin/users/{login_alice}", follow_redirects=False)
        assert r.status_code == 302


class TestOverview:
    """Übersicht des Admin-Panels (NUTZ-7, NUTZ-12)."""

    def _total(self, app, user_id):
        from app import running_total
        with app.app_context():
            return running_total(db.session.get(User, user_id))[0]

    def test_team_total_sums_active_users(self, client, login_admin, app, alice_id, bob_id,
                                          inactive_user_id, make_workday):
        """NUTZ-12: Summe der Gesamtsalden aller aktiven Nutzerinnen."""
        make_workday(alice_id, date.today() - timedelta(days=1), time(8, 0), time(18, 0))
        make_workday(inactive_user_id, date.today() - timedelta(days=1), time(8, 0), time(20, 0))
        expected = self._total(app, alice_id) + self._total(app, bob_id)
        text = " ".join(client.get("/admin").data.decode().split())
        assert f'Summe Gesamtsaldo</div> <div class="zf-team-total' in text
        assert f"{logic.format_hm(expected, signed=True)} h" in text
        assert "<td>Summe</td>" in text

    def test_no_attention_cards(self, client, login_admin, alice_id, make_workday):
        """NUTZ-11 entfallen: keine Karten zu Stempelungen oder fehlenden Tagen."""
        make_workday(alice_id, date.today() - timedelta(days=3), time(8, 0), None)
        html = client.get("/admin").data.decode()
        assert "Jetzt eingestempelt" not in html
        assert "Offene Stempelungen" not in html
        assert "Fehlende Tage" not in html

    def test_inactive_users_collapsed(self, client, login_admin, alice_id, inactive_user_id):
        html = client.get("/admin").data.decode()
        assert "Deaktiviert (1)" in html
        assert html.index("Deaktiviert (1)") > html.index(">Alice</a>")

    def test_settings_saved_on_settings_page(self, client, login_admin):
        r = client.post("/admin/settings", data={"yearly_reset": "1"})
        assert r.headers["Location"].endswith("/admin/settings")
