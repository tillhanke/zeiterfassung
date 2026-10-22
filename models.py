"""Datenmodelle für die Zeiterfassung."""
from __future__ import annotations

from datetime import date, time
from typing import Optional

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index, UniqueConstraint

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    weekly_hours = db.Column(db.Float, nullable=False, default=40.0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    # Optionaler Stichtag: Einträge davor zählen nicht mehr, stattdessen gilt
    # start_balance (Überstunden, auch negativ) als Saldo zu Beginn dieses Tages.
    start_date: Optional[date] = db.Column(db.Date, nullable=True)
    start_balance = db.Column(db.Float, nullable=False, default=0.0, server_default="0")

    workdays = db.relationship(
        "WorkDay", backref="user", cascade="all, delete-orphan", lazy="dynamic"
    )
    absences = db.relationship(
        "Absence", backref="user", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def daily_target(self) -> float:
        # Soll-Stunden pro Werktag (Mo-Fr); Wochenstunden gleichmäßig auf 5 Tage verteilt.
        return self.weekly_hours / 5.0

    def __repr__(self) -> str:
        return f"<User {self.id} {self.name}>"


class WorkDay(db.Model):
    """Ein Arbeitszeitfenster. Pro Tag sind mehrere Fenster möglich; die
    gesetzliche Pause wird je Fenster separat bestimmt (siehe logic.py).

    end_time = None bedeutet: das Fenster läuft noch (per "Anfang" gestartet,
    "Ende" noch nicht gedrückt). Laufende Fenster zählen noch nicht in die Summen.
    """

    __tablename__ = "workdays"
    __table_args__ = (Index("ix_workdays_user_date", "user_id", "date"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date: date = db.Column(db.Date, nullable=False)
    start_time: time = db.Column(db.Time, nullable=False)
    end_time: Optional[time] = db.Column(db.Time, nullable=True)

    def __repr__(self) -> str:
        return f"<WorkDay user={self.user_id} {self.date} {self.start_time}-{self.end_time}>"


class Absence(db.Model):
    __tablename__ = "absences"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_absence_user_date"),)

    KIND_VACATION = "vacation"
    KIND_SICK = "sick"
    VALID_KINDS = (KIND_VACATION, KIND_SICK)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date: date = db.Column(db.Date, nullable=False)
    kind = db.Column(db.String(16), nullable=False)

    def __repr__(self) -> str:
        return f"<Absence user={self.user_id} {self.date} {self.kind}>"
