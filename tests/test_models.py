"""Tests für Datenmodelle: Constraints, Eigenschaften, Cascade-Verhalten."""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy.exc import IntegrityError

from models import Absence, User, WorkDay


class TestUser:
    def test_create_user_defaults(self, db):
        u = User(name="Max", weekly_hours=40.0)
        db.session.add(u)
        db.session.commit()
        assert u.id is not None
        assert u.active is True
        assert u.weekly_hours == 40.0

    def test_daily_target_property(self, db):
        u = User(name="Max", weekly_hours=40.0)
        db.session.add(u)
        db.session.commit()
        assert u.daily_target == 8.0

        u2 = User(name="Halbtags", weekly_hours=20.0)
        db.session.add(u2)
        db.session.commit()
        assert u2.daily_target == 4.0

    def test_name_must_be_unique(self, db):
        db.session.add(User(name="Same", weekly_hours=40))
        db.session.commit()
        db.session.add(User(name="Same", weekly_hours=20))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_repr(self, db):
        u = User(name="Test", weekly_hours=40)
        db.session.add(u)
        db.session.commit()
        assert "User" in repr(u)
        assert "Test" in repr(u)


class TestWorkDay:
    def test_create(self, db):
        u = User(name="A", weekly_hours=40)
        db.session.add(u)
        db.session.commit()
        wd = WorkDay(user_id=u.id, date=date(2026, 5, 11), start_time=time(9, 0), end_time=time(17, 0))
        db.session.add(wd)
        db.session.commit()
        assert wd.id is not None

    def test_unique_user_date(self, db):
        u = User(name="A", weekly_hours=40)
        db.session.add(u)
        db.session.commit()
        d = date(2026, 5, 11)
        db.session.add(WorkDay(user_id=u.id, date=d, start_time=time(9, 0), end_time=time(17, 0)))
        db.session.commit()
        db.session.add(WorkDay(user_id=u.id, date=d, start_time=time(10, 0), end_time=time(18, 0)))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_same_date_for_different_users_ok(self, db):
        a = User(name="A", weekly_hours=40)
        b = User(name="B", weekly_hours=40)
        db.session.add_all([a, b])
        db.session.commit()
        d = date(2026, 5, 11)
        db.session.add(WorkDay(user_id=a.id, date=d, start_time=time(9, 0), end_time=time(17, 0)))
        db.session.add(WorkDay(user_id=b.id, date=d, start_time=time(9, 0), end_time=time(17, 0)))
        db.session.commit()  # darf nicht crashen


class TestAbsence:
    def test_kinds_constants(self):
        assert Absence.KIND_VACATION == "vacation"
        assert Absence.KIND_SICK == "sick"
        assert "vacation" in Absence.VALID_KINDS
        assert "sick" in Absence.VALID_KINDS

    def test_unique_user_date(self, db):
        u = User(name="A", weekly_hours=40)
        db.session.add(u)
        db.session.commit()
        d = date(2026, 5, 11)
        db.session.add(Absence(user_id=u.id, date=d, kind=Absence.KIND_VACATION))
        db.session.commit()
        db.session.add(Absence(user_id=u.id, date=d, kind=Absence.KIND_SICK))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


class TestCascade:
    def test_delete_user_removes_workdays_and_absences(self, db):
        u = User(name="A", weekly_hours=40)
        db.session.add(u)
        db.session.commit()
        uid = u.id
        db.session.add(WorkDay(user_id=uid, date=date(2026, 5, 11), start_time=time(9, 0), end_time=time(17, 0)))
        db.session.add(Absence(user_id=uid, date=date(2026, 5, 12), kind="vacation"))
        db.session.commit()

        db.session.delete(u)
        db.session.commit()

        assert WorkDay.query.filter_by(user_id=uid).count() == 0
        assert Absence.query.filter_by(user_id=uid).count() == 0
