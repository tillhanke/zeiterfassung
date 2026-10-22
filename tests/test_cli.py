"""Tests für die Flask-CLI-Befehle (init-db, reset-db) und die
Alembic-Migrationen (ADR-0012)."""
from __future__ import annotations

from datetime import date, time

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from flask_migrate import upgrade
from sqlalchemy import inspect, text

from app import MIGRATIONS_DIR
from models import Absence, User, WorkDay, db


def _head() -> str:
    return ScriptDirectory(MIGRATIONS_DIR).get_current_head()


def _db_revision() -> str | None:
    with db.engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


class TestInitDb:
    def test_runs_without_error(self, runner):
        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0
        assert "Datenbank initialisiert" in result.output

    def test_idempotent(self, runner):
        runner.invoke(args=["init-db"])
        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0

    def test_empty_database_gets_schema_and_head_revision(self, app, runner):
        with app.app_context():
            db.drop_all()
            assert inspect(db.engine).get_table_names() == []

        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0

        with app.app_context():
            tables = set(inspect(db.engine).get_table_names())
            assert {"users", "workdays", "absences", "settings", "alembic_version"} <= tables
            assert _db_revision() == _head()

    def test_existing_database_without_alembic_is_adopted(self, app, runner):
        """Bestehende DB aus der Zeit vor Alembic: Daten bleiben, Revision wird gesetzt."""
        with app.app_context():
            db.session.add(User(name="Bestand", weekly_hours=30))
            db.session.commit()
            assert _db_revision() is None

        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0

        with app.app_context():
            assert _db_revision() == _head()
            assert User.query.one().name == "Bestand"


class TestMigrationsMatchModels:
    def test_no_difference_between_migrations_and_models(self, app):
        """Neue Modelländerungen brauchen eine Migration (`flask db migrate`)."""
        with app.app_context():
            db.drop_all()
            upgrade()
            with db.engine.connect() as conn:
                diff = compare_metadata(MigrationContext.configure(conn), db.metadata)
            assert diff == []


class TestMigrateWorkdays:
    OLD_DDL = (
        "CREATE TABLE workdays ("
        "id INTEGER NOT NULL, user_id INTEGER NOT NULL, date DATE NOT NULL, "
        "start_time TIME NOT NULL, end_time TIME NOT NULL, PRIMARY KEY (id), "
        "CONSTRAINT uq_workday_user_date UNIQUE (user_id, date), "
        "FOREIGN KEY(user_id) REFERENCES users (id))"
    )

    def test_old_schema_is_migrated_and_data_kept(self, app, runner):
        with app.app_context():
            db.session.execute(text("DROP TABLE workdays"))
            db.session.execute(text(self.OLD_DDL))
            u = User(name="Alt", weekly_hours=40)
            db.session.add(u)
            db.session.commit()
            db.session.execute(
                text(
                    "INSERT INTO workdays (id, user_id, date, start_time, end_time) "
                    "VALUES (7, :uid, '2026-05-11', '09:00:00.000000', '17:00:00.000000')"
                ),
                {"uid": u.id},
            )
            db.session.commit()
            uid = u.id

        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0

        with app.app_context():
            assert inspect(db.engine).get_unique_constraints("workdays") == []
            wd = db.session.get(WorkDay, 7)
            assert (wd.user_id, wd.date, wd.start_time) == (uid, date(2026, 5, 11), time(9, 0))
            # Zweites Fenster am selben Tag ist jetzt möglich.
            db.session.add(
                WorkDay(user_id=uid, date=date(2026, 5, 11), start_time=time(18, 0), end_time=time(19, 0))
            )
            db.session.commit()
            assert WorkDay.query.count() == 2

        # Zweiter Lauf ist ein No-op.
        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0


class TestMigrateEndTimeNullable:
    def test_not_null_end_time_is_relaxed(self, app, runner):
        with app.app_context():
            db.session.execute(text("DROP TABLE workdays"))
            db.session.execute(
                text(
                    "CREATE TABLE workdays (id INTEGER NOT NULL, user_id INTEGER NOT NULL, "
                    "date DATE NOT NULL, start_time TIME NOT NULL, end_time TIME NOT NULL, "
                    "PRIMARY KEY (id), FOREIGN KEY(user_id) REFERENCES users (id))"
                )
            )
            # Index wie in DBs aus dem Mehrfenster-Release (wandert beim RENAME mit).
            db.session.execute(text("CREATE INDEX ix_workdays_user_date ON workdays (user_id, date)"))
            u = User(name="Alt", weekly_hours=40)
            db.session.add(u)
            db.session.commit()
            uid = u.id

        result = runner.invoke(args=["init-db"])
        assert result.exit_code == 0

        with app.app_context():
            indexes = {ix["name"] for ix in inspect(db.engine).get_indexes("workdays")}
            assert indexes == {"ix_workdays_user_date"}
            db.session.add(WorkDay(user_id=uid, date=date(2026, 5, 11), start_time=time(8, 0), end_time=None))
            db.session.commit()
            assert WorkDay.query.one().end_time is None


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

    def test_reset_sets_head_revision(self, app, runner):
        runner.invoke(args=["reset-db"])
        with app.app_context():
            assert _db_revision() == _head()
