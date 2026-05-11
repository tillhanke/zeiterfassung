"""Tests für die Flask-CLI-Befehle (init-db, reset-db)."""
from __future__ import annotations

from datetime import date, time

from models import Absence, User, WorkDay, db


class TestInitDb:
    def test_runs_without_error(self, runner):
        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0
        assert "Datenbank initialisiert" in result.output

    def test_idempotent(self, runner):
        runner.invoke(args=["init-db"])
        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0


class TestResetDb:
    def test_clears_all_data(self, app, runner):
        with app.app_context():
            u = User(name="ToDelete", weekly_hours=40)
            db.session.add(u)
            db.session.commit()
            db.session.add(
                WorkDay(
                    user_id=u.id,
                    date=date(2026, 5, 11),
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                )
            )
            db.session.add(
                Absence(user_id=u.id, date=date(2026, 5, 12), kind="vacation")
            )
            db.session.commit()

        result = runner.invoke(args=["reset-db"])
        assert result.exit_code == 0
        assert "zur\u00fcckgesetzt" in result.output

        with app.app_context():
            assert User.query.count() == 0
            assert WorkDay.query.count() == 0
            assert Absence.query.count() == 0

    def test_tables_exist_after_reset(self, app, runner):
        runner.invoke(args=["reset-db"])
        with app.app_context():
            # Anlegen muss weiterhin funktionieren -> Tabellen existieren.
            u = User(name="X", weekly_hours=40)
            db.session.add(u)
            db.session.commit()
            assert u.id is not None
