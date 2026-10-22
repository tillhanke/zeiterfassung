"""Tests für den Inaktivitäts-Timeout (Rückkehr zur Willkommensseite)."""
from __future__ import annotations

import pytest

import app as app_module


@pytest.fixture
def clock(monkeypatch):
    """Steuerbare Uhr für app._epoch (Sekunden)."""

    class Clock:
        now = 1_000_000.0

        def advance(self, seconds: float) -> None:
            self.now += seconds

    c = Clock()
    monkeypatch.setattr(app_module, "_epoch", lambda: c.now)
    return c


def _login(client, alice_id):
    return client.post("/switch", data={"identity": f"user:{alice_id}"})


def _identity(client):
    with client.session_transaction() as sess:
        return sess.get("identity")


class TestServerSide:
    def test_activity_within_timeout_keeps_session(self, client, alice_id, clock):
        _login(client, alice_id)
        clock.advance(599)
        r = client.get(f"/user/{alice_id}")
        assert r.status_code == 200
        assert _identity(client) == f"user:{alice_id}"

    def test_each_request_resets_timer(self, client, alice_id, clock):
        _login(client, alice_id)
        for _ in range(3):
            clock.advance(500)
            assert client.get(f"/user/{alice_id}").status_code == 200
        assert _identity(client) == f"user:{alice_id}"

    def test_expired_session_redirects_to_welcome(self, client, alice_id, clock):
        _login(client, alice_id)
        clock.advance(601)
        r = client.get(f"/user/{alice_id}")
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/")
        assert _identity(client) is None
        page = client.get("/").data.decode()
        assert "Willkommen" in page
        assert "Inaktivität" in page

    def test_expired_post_is_not_executed(self, client, alice_id, clock, app):
        from models import Absence

        _login(client, alice_id)
        clock.advance(601)
        r = client.post(
            f"/user/{alice_id}/entry",
            data={"kind": "vacation", "date": "2026-05-11"},
        )
        assert r.status_code == 302
        with app.app_context():
            assert Absence.query.count() == 0

    def test_admin_also_times_out(self, client, clock):
        client.post("/switch", data={"identity": "admin"})
        clock.advance(601)
        r = client.get("/admin")
        assert r.status_code == 302
        assert _identity(client) is None

    def test_timeout_configurable(self, tmp_path, alice_id, clock):
        app = app_module.create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path}/t.db",
                "IDLE_TIMEOUT_SECONDS": 60,
            }
        )
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["identity"] = "admin"
            sess["last_activity"] = clock.now
        clock.advance(61)
        assert c.get("/admin").status_code == 302


class TestKeepalive:
    def test_keepalive_extends_session(self, client, alice_id, clock):
        _login(client, alice_id)
        clock.advance(500)
        assert client.post("/keepalive").status_code == 204
        clock.advance(500)
        assert client.get(f"/user/{alice_id}").status_code == 200

    def test_keepalive_after_expiry_returns_401(self, client, alice_id, clock):
        _login(client, alice_id)
        clock.advance(601)
        assert client.post("/keepalive").status_code == 401
        assert _identity(client) is None

    def test_keepalive_without_identity(self, client):
        assert client.post("/keepalive").status_code == 401


class TestTimeoutRoute:
    def test_logs_out_when_idle(self, client, alice_id, clock):
        _login(client, alice_id)
        clock.advance(595)  # Browser-Timer feuert, Server-Zeitstempel minimal jünger
        r = client.get("/timeout")
        assert r.status_code == 302
        assert _identity(client) is None

    def test_keeps_session_if_other_tab_was_active(self, client, alice_id, clock):
        _login(client, alice_id)
        clock.advance(300)
        client.post("/keepalive")  # anderer Tab aktiv
        clock.advance(300)
        client.get("/timeout")  # inaktiver Tab will abmelden
        assert _identity(client) == f"user:{alice_id}"

    def test_does_not_refresh_activity(self, client, alice_id, clock):
        _login(client, alice_id)
        clock.advance(400)
        client.get("/timeout")
        clock.advance(201)
        r = client.get(f"/user/{alice_id}")
        assert r.status_code == 302


class TestClientScript:
    def test_script_present_when_logged_in(self, client, alice_id):
        _login(client, alice_id)
        html = client.get(f"/user/{alice_id}").data.decode()
        assert "const TIMEOUT_MS = 600000;" in html
        assert "/timeout" in html
        assert "/keepalive" in html

    def test_warning_before_logout(self, client, alice_id):
        """NUTZ-3: eine Minute vorher erscheint ein Hinweis mit Countdown."""
        _login(client, alice_id)
        html = client.get(f"/user/{alice_id}").data.decode()
        assert 'id="idleWarning"' in html
        assert "const WARN_MS = Math.min(60 * 1000, TIMEOUT_MS / 2);" in html
        assert ">Weiter arbeiten</button>" in html

    def test_no_script_on_welcome_page(self, client):
        html = client.get("/").data.decode()
        assert "TIMEOUT_MS" not in html
