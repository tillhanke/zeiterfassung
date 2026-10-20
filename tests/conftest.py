"""Gemeinsame pytest-Fixtures.

Jeder Test bekommt eine frische Flask-App mit einer eigenen, leeren
SQLite-Datei in `tmp_path`. Damit sind die Tests vollkommen isoliert
und können auch parallelisiert werden.
"""
from __future__ import annotations

from datetime import date, time
from typing import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from models import Absence, User, WorkDay, db as _db


@pytest.fixture
def app(tmp_path) -> Iterator[Flask]:
    # Config muss an create_app() übergeben werden: Flask-SQLAlchemy bindet die
    # Engine in init_app(); ein späteres config.update() würde ignoriert und die
    # Tests liefen gegen instance/zeiterf.db (inkl. drop_all am Ende!).
    flask_app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path}/test.db",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with flask_app.app_context():
        _db.create_all()
    yield flask_app
    with flask_app.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def runner(app: Flask):
    return app.test_cli_runner()


@pytest.fixture
def db(app: Flask):
    """Direkter DB-Zugriff in einem App-Kontext."""
    with app.app_context():
        yield _db


# ---------------------------------------------------------------------------
# User-Fixtures
# ---------------------------------------------------------------------------


def _create_user(name: str, weekly_hours: float = 40.0, active: bool = True) -> int:
    u = User(name=name, weekly_hours=weekly_hours, active=active)
    _db.session.add(u)
    _db.session.commit()
    return u.id


@pytest.fixture
def alice_id(app: Flask) -> int:
    """User Alice (40 h/Woche, daily_target=8.0)."""
    with app.app_context():
        return _create_user("Alice", 40.0)


@pytest.fixture
def bob_id(app: Flask) -> int:
    """User Bob (20 h/Woche, daily_target=4.0)."""
    with app.app_context():
        return _create_user("Bob", 20.0)


@pytest.fixture
def inactive_user_id(app: Flask) -> int:
    with app.app_context():
        return _create_user("Inaktiv", 40.0, active=False)


@pytest.fixture
def login_alice(client: FlaskClient, alice_id: int) -> int:
    with client.session_transaction() as sess:
        sess["identity"] = f"user:{alice_id}"
    return alice_id


@pytest.fixture
def login_bob(client: FlaskClient, bob_id: int) -> int:
    with client.session_transaction() as sess:
        sess["identity"] = f"user:{bob_id}"
    return bob_id


@pytest.fixture
def login_admin(client: FlaskClient) -> None:
    with client.session_transaction() as sess:
        sess["identity"] = "admin"


# ---------------------------------------------------------------------------
# Hilfs-Konstanten (von mehreren Tests genutzt)
# ---------------------------------------------------------------------------


@pytest.fixture
def make_workday(app: Flask):
    """Factory: legt einen WorkDay an und committet."""

    def _make(user_id: int, d: date, start: time = time(9, 0), end: time = time(17, 30)):
        with app.app_context():
            wd = WorkDay(user_id=user_id, date=d, start_time=start, end_time=end)
            _db.session.add(wd)
            _db.session.commit()
            return wd.id

    return _make


@pytest.fixture
def make_absence(app: Flask):
    def _make(user_id: int, d: date, kind: str = Absence.KIND_VACATION):
        with app.app_context():
            a = Absence(user_id=user_id, date=d, kind=kind)
            _db.session.add(a)
            _db.session.commit()
            return a.id

    return _make
