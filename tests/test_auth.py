"""Tests für Identitäts-Wechsel, Schutz von Routen und Zugriffsisolation."""
from __future__ import annotations


class TestIndex:
    def test_anonymous_index_renders(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"Willkommen" in r.data

    def test_anonymous_index_lists_active_users(self, client, alice_id, bob_id, inactive_user_id):
        r = client.get("/")
        assert b"Alice" in r.data
        assert b"Bob" in r.data
        assert b"Inaktiv" not in r.data  # inaktive User werden nicht gelistet

    def test_admin_sees_start_page(self, client, login_admin, alice_id):
        """UI-3: Startseite zeigt auch mit aktiver Identität die Namensauswahl."""
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 200
        assert b"Alice" in r.data
        with client.session_transaction() as s:
            assert s["identity"] == "admin"  # Identität bleibt bis „Abmelden“

    def test_user_sees_start_page(self, client, login_alice):
        """UI-3: Startseite zeigt auch mit aktiver Identität die Namensauswahl."""
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 200
        assert b"zf-tile" in r.data
        assert b">Abmelden</button>" in r.data


class TestSwitch:
    def test_switch_to_admin(self, client):
        r = client.post("/switch", data={"identity": "admin"}, follow_redirects=False)
        assert r.status_code == 302
        assert "/admin" in r.headers["Location"]
        with client.session_transaction() as s:
            assert s["identity"] == "admin"

    def test_switch_to_user(self, client, alice_id):
        r = client.post("/switch", data={"identity": f"user:{alice_id}"}, follow_redirects=False)
        assert r.status_code == 302
        assert f"/user/{alice_id}" in r.headers["Location"]
        with client.session_transaction() as s:
            assert s["identity"] == f"user:{alice_id}"

    def test_switch_to_inactive_user_404(self, client, inactive_user_id):
        r = client.post("/switch", data={"identity": f"user:{inactive_user_id}"})
        assert r.status_code == 404

    def test_switch_to_unknown_user_404(self, client):
        r = client.post("/switch", data={"identity": "user:99999"})
        assert r.status_code == 404

    def test_switch_invalid_user_id_400(self, client):
        r = client.post("/switch", data={"identity": "user:abc"})
        assert r.status_code == 400

    def test_switch_empty_clears_identity(self, client, login_alice):
        r = client.post("/switch", data={"identity": ""}, follow_redirects=False)
        assert r.status_code == 302
        with client.session_transaction() as s:
            assert "identity" not in s

    def test_switch_unknown_value_400(self, client):
        r = client.post("/switch", data={"identity": "garbage"})
        assert r.status_code == 400


class TestRouteProtection:
    def test_admin_page_requires_admin_identity(self, client):
        r = client.get("/admin", follow_redirects=False)
        # Decorator redirected uns auf "/"
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/")

    def test_admin_page_redirects_normal_user(self, client, login_alice):
        r = client.get("/admin", follow_redirects=False)
        assert r.status_code == 302

    def test_admin_page_accessible_for_admin(self, client, login_admin):
        r = client.get("/admin")
        assert r.status_code == 200
        assert b"\xc3\x9cbersicht" in r.data

    def test_anonymous_cannot_access_user_dashboard(self, client, alice_id):
        r = client.get(f"/user/{alice_id}")
        assert r.status_code == 403

    def test_user_cannot_access_other_user_dashboard(self, client, login_alice, bob_id):
        r = client.get(f"/user/{bob_id}")
        assert r.status_code == 403

    def test_user_cannot_access_other_user_entry_form(self, client, login_alice, bob_id):
        r = client.get(f"/user/{bob_id}/entry")
        assert r.status_code == 403

    def test_user_cannot_post_to_other_user_entry(self, client, login_alice, bob_id):
        r = client.post(
            f"/user/{bob_id}/entry",
            data={"kind": "work", "date": "2026-05-11", "start_time": "09:00", "end_time": "17:00"},
        )
        assert r.status_code == 403

    def test_user_cannot_delete_other_user_day(self, client, login_alice, bob_id):
        r = client.post(f"/user/{bob_id}/day/2026-05-11/delete")
        assert r.status_code == 403

    def test_user_cannot_access_other_user_bulk(self, client, login_alice, bob_id):
        r = client.get(f"/user/{bob_id}/bulk-entry")
        assert r.status_code == 403

    def test_admin_can_access_any_user_dashboard(self, client, login_admin, alice_id):
        r = client.get(f"/user/{alice_id}")
        assert r.status_code == 200

    def test_admin_user_id_404_for_unknown(self, client, login_admin):
        r = client.get("/user/99999")
        assert r.status_code == 404

    def test_user_creating_admin_user_create_redirect(self, client, login_alice):
        # /admin/users sind admin-only.
        r = client.post("/admin/users", data={"name": "X", "weekly_hours": "40"}, follow_redirects=False)
        assert r.status_code == 302  # Decorator redirected zu /
