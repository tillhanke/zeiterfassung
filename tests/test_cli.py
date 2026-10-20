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


class TestMigrateWorkdays:
    OLD_DDL = (
        "CREATE TABLE workdays ("
        "id INTEGER NOT NULL, user_id INTEGER NOT NULL, date DATE NOT NULL, "
        "start_time TIME NOT NULL, end_time TIME NOT NULL, PRIMARY KEY (id), "
        "CONSTRAINT uq_workday_user_date UNIQUE (user_id, date), "
        "FOREIGN KEY(user_id) REFERENCES users (id))"
    )

    def test_old_schema_is_migrated_and_data_kept(self, app, runner):
        from sqlalchemy import text

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
        assert "migriert" in result.output

        with app.app_context():
            wd = db.session.get(WorkDay, 7)
            assert (wd.user_id, wd.date, wd.start_time) == (uid, date(2026, 5, 11), time(9, 0))
            # Zweites Fenster am selben Tag ist jetzt möglich.
            db.session.add(
                WorkDay(user_id=uid, date=date(2026, 5, 11), start_time=time(18, 0), end_time=time(19, 0))
            )
            db.session.commit()
            assert WorkDay.query.count() == 2

        # Zweiter Lauf: nichts mehr zu migrieren.
        result = runner.invoke(args=["init-db"])
        assert "migriert" not in result.output


class TestMigrateEndTimeNullable:
    def test_not_null_end_time_is_relaxed(self, app, runner):
        from sqlalchemy import text

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
        assert "migriert" in result.output

        with app.app_context():
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
