"""Tests für das Admin-Panel und User-Verwaltung."""
from __future__ import annotations

from models import User


class TestAdminPanel:
    def test_panel_renders(self, client, login_admin, alice_id, bob_id):
        r = client.get("/admin")
        assert r.status_code == 200
        assert b"Admin-Panel" in r.data
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
