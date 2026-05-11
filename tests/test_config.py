"""Tests für die App-Konfiguration (SECRET_KEY-Quelle, DB-Pfad)."""
from __future__ import annotations


class TestSecretKey:
    def test_env_variable_used(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "aus-der-umgebung")
        # create_app frisch importieren/aufrufen, damit os.environ neu gelesen wird.
        from app import create_app

        app = create_app()
        assert app.config["SECRET_KEY"] == "aus-der-umgebung"

    def test_empty_env_falls_back_to_dev_default(self, monkeypatch):
        # Leerer SECRET_KEY soll NICHT akzeptiert werden (-> Fallback).
        monkeypatch.setenv("SECRET_KEY", "")
        from app import create_app

        app = create_app()
        assert app.config["SECRET_KEY"] == "dev-secret-key-change-me"

    def test_unset_env_falls_back_to_dev_default(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        from app import create_app

        app = create_app()
        assert app.config["SECRET_KEY"] == "dev-secret-key-change-me"


class TestSqliteUri:
    def test_uri_points_into_instance(self):
        from app import create_app

        app = create_app()
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        assert uri.startswith("sqlite:///")
        assert uri.endswith("/zeiterf.db")
        # Liegt im instance-Pfad des Apps.
        assert app.instance_path in uri
