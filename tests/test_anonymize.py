"""Tests für die Namens-Anonymisierung (anonymize_user_names + CLI)."""
from __future__ import annotations

from datetime import date, time

from app import anonymize_user_names
from models import Absence, User, WorkDay, db


class TestAnonymizeFunction:
    def test_empty_db_returns_zero(self, app):
        with app.app_context():
            assert anonymize_user_names() == 0

    def test_renames_users_in_id_order(self, app):
        with app.app_context():
            db.session.add_all(
                [
                    User(name="Charlie", weekly_hours=40),
                    User(name="Alice", weekly_hours=20),
                    User(name="Bob", weekly_hours=35),
                ]
            )
            db.session.commit()
            n = anonymize_user_names()
            assert n == 3
            users = User.query.order_by(User.id).all()
            assert [u.name for u in users] == ["Nutzerin 1", "Nutzerin 2", "Nutzerin 3"]

    def test_custom_prefix(self, app):
        with app.app_context():
            db.session.add_all([User(name="X", weekly_hours=40), User(name="Y", weekly_hours=40)])
            db.session.commit()
            anonymize_user_names(prefix="User")
            names = sorted(u.name for u in User.query.all())
            assert names == ["User 1", "User 2"]

    def test_preserves_ids(self, app):
        with app.app_context():
            db.session.add_all(
                [User(name="A", weekly_hours=40), User(name="B", weekly_hours=40)]
            )
            db.session.commit()
            ids_before = sorted(u.id for u in User.query.all())
            anonymize_user_names()
            ids_after = sorted(u.id for u in User.query.all())
            assert ids_before == ids_after

    def test_preserves_weekly_hours_and_active(self, app):
        with app.app_context():
            db.session.add_all(
                [
                    User(name="A", weekly_hours=37.5, active=True),
                    User(name="B", weekly_hours=20.0, active=False),
                ]
            )
            db.session.commit()
            anonymize_user_names()
            users = User.query.order_by(User.id).all()
            assert users[0].weekly_hours == 37.5
            assert users[0].active is True
            assert users[1].weekly_hours == 20.0
            assert users[1].active is False

    def test_preserves_workdays_and_absences(self, app):
        with app.app_context():
            u = User(name="Vor", weekly_hours=40)
            db.session.add(u)
            db.session.commit()
            uid = u.id
            db.session.add_all(
                [
                    WorkDay(
                        user_id=uid,
                        date=date(2026, 5, 11),
                        start_time=time(9, 0),
                        end_time=time(17, 30),
                    ),
                    WorkDay(
                        user_id=uid,
                        date=date(2026, 5, 12),
                        start_time=time(8, 0),
                        end_time=time(16, 30),
                    ),
                    Absence(user_id=uid, date=date(2026, 5, 13), kind="vacation"),
                ]
            )
            db.session.commit()

            anonymize_user_names()

            wds = WorkDay.query.filter_by(user_id=uid).order_by(WorkDay.date).all()
            absences = Absence.query.filter_by(user_id=uid).all()
            assert len(wds) == 2
            assert wds[0].date == date(2026, 5, 11)
            assert wds[0].start_time == time(9, 0)
            assert wds[0].end_time == time(17, 30)
            assert wds[1].date == date(2026, 5, 12)
            assert wds[1].start_time == time(8, 0)
            assert wds[1].end_time == time(16, 30)
            assert len(absences) == 1
            assert absences[0].date == date(2026, 5, 13)
            assert absences[0].kind == "vacation"

    def test_idempotent_second_run_no_error(self, app):
        with app.app_context():
            db.session.add_all(
                [User(name="A", weekly_hours=40), User(name="B", weekly_hours=40)]
            )
            db.session.commit()
            anonymize_user_names()
            first = sorted(u.name for u in User.query.all())
            anonymize_user_names()
            second = sorted(u.name for u in User.query.all())
            assert first == second == ["Nutzerin 1", "Nutzerin 2"]

    def test_handles_swap_like_collision(self, app):
        """Wenn ein User bereits 'Nutzerin 1' heißt und ein anderer noch nicht,
        darf die zwei-Phasen-Umbenennung nicht am UNIQUE-Constraint scheitern.
        """
        with app.app_context():
            db.session.add_all(
                [
                    User(name="Nutzerin 2", weekly_hours=40),  # niedrigere ID
                    User(name="Nutzerin 1", weekly_hours=40),  # höhere ID
                ]
            )
            db.session.commit()
            # Reihenfolge wäre nun id=1 -> "Nutzerin 1" (war "Nutzerin 2"),
            # id=2 -> "Nutzerin 2" (war "Nutzerin 1") -- klassischer Swap.
            anonymize_user_names()
            users = User.query.order_by(User.id).all()
            assert users[0].name == "Nutzerin 1"
            assert users[1].name == "Nutzerin 2"

    def test_includes_inactive_users(self, app):
        with app.app_context():
            db.session.add_all(
                [
                    User(name="A", weekly_hours=40, active=True),
                    User(name="B", weekly_hours=40, active=False),
                ]
            )
            db.session.commit()
            anonymize_user_names()
            # Auch inaktive User werden umbenannt.
            assert User.query.filter(User.name.like("Nutzerin %")).count() == 2


class TestAnonymizeCli:
    def test_default_prefix_with_yes(self, app, runner):
        with app.app_context():
            db.session.add_all(
                [User(name="A", weekly_hours=40), User(name="B", weekly_hours=40)]
            )
            db.session.commit()
        result = runner.invoke(args=["anonymize-names", "--yes"])
        assert result.exit_code == 0
        assert "2 Nutzerin(nen) anonymisiert" in result.output
        with app.app_context():
            names = sorted(u.name for u in User.query.all())
            assert names == ["Nutzerin 1", "Nutzerin 2"]

    def test_custom_prefix(self, app, runner):
        with app.app_context():
            db.session.add(User(name="A", weekly_hours=40))
            db.session.commit()
        result = runner.invoke(args=["anonymize-names", "--prefix", "Mensch", "--yes"])
        assert result.exit_code == 0
        with app.app_context():
            assert User.query.one().name == "Mensch 1"

    def test_empty_db_short_circuit(self, app, runner):
        result = runner.invoke(args=["anonymize-names", "--yes"])
        assert result.exit_code == 0
        assert "Keine Nutzerinnen" in result.output

    def test_aborts_without_confirmation(self, app, runner):
        with app.app_context():
            db.session.add(User(name="Original", weekly_hours=40))
            db.session.commit()
        # Auf die Bestätigung mit "n" antworten -> Abbruch.
        result = runner.invoke(args=["anonymize-names"], input="n\n")
        assert result.exit_code != 0  # click.confirm(abort=True) liefert non-zero
        with app.app_context():
            assert User.query.one().name == "Original"

    def test_proceeds_with_yes_input(self, app, runner):
        with app.app_context():
            db.session.add(User(name="Original", weekly_hours=40))
            db.session.commit()
        result = runner.invoke(args=["anonymize-names"], input="y\n")
        assert result.exit_code == 0
        with app.app_context():
            assert User.query.one().name == "Nutzerin 1"
