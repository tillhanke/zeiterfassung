"""Flask-Anwendung für die Zeiterfassung.

Startbefehle:
    flask --app app init-db    # legt die Tabellen an
    flask --app app reset-db   # leert die Datenbank (alle Nutzerinnen + Einträge)
    flask --app app run --debug
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Optional

import click
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import logic
from models import Absence, User, WorkDay, db


def create_app(test_config: Optional[dict] = None) -> Flask:
    app = Flask(__name__)
    # SECRET_KEY MUSS in Produktion über die Umgebungsvariable gesetzt werden.
    # Der Dev-Fallback ist absichtlich unsicher und wird nur akzeptiert, wenn
    # FLASK_ENV/SECRET_KEY nicht gesetzt sind – siehe Warnung bei Produktion.
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or "dev-secret-key-change-me",
        SQLALCHEMY_DATABASE_URI="sqlite:///zeiterf.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    # SQLite im instance-Folder ablegen, damit es bei `flask run` automatisch
    # entsteht. In Docker wird das Verzeichnis als Volume gemountet.
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"sqlite:///{app.instance_path}/zeiterf.db"
    )
    os.makedirs(app.instance_path, exist_ok=True)

    # Overrides (z. B. Test-DB) MÜSSEN vor db.init_app greifen: Flask-SQLAlchemy
    # legt die Engine dort bereits an und ignoriert spätere Config-Änderungen.
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    register_routes(app)
    register_cli(app)
    register_context(app)

    return app


# ---------------------------------------------------------------------------
# Identitäts-Handling (kein echtes Auth, nur Session-Switch)
# ---------------------------------------------------------------------------


def current_identity() -> Optional[str]:
    return session.get("identity")


def current_user() -> Optional[User]:
    ident = current_identity()
    if not ident or not ident.startswith("user:"):
        return None
    try:
        uid = int(ident.split(":", 1)[1])
    except ValueError:
        return None
    return db.session.get(User, uid)


def require_identity(role: str):
    """Decorator: prüft Session-Identität.

    role='admin' verlangt 'admin'.
    role='user' verlangt eine 'user:<id>'-Identität.
    role='self' wird in den Routen separat behandelt, hier nur 'admin' oder 'user'.
    """

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ident = current_identity()
            if role == "admin" and ident != "admin":
                flash("Bitte zur Admin-Ansicht wechseln.", "warning")
                return redirect(url_for("index"))
            if role == "user" and (not ident or not ident.startswith("user:")):
                flash("Bitte zuerst eine Nutzerin auswählen.", "warning")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)

        return wrapper

    return deco


# ---------------------------------------------------------------------------
# Context Processor: Topbar braucht User-Liste und aktive Identität
# ---------------------------------------------------------------------------


def register_context(app: Flask) -> None:
    @app.context_processor
    def inject_topbar():
        try:
            users = User.query.filter_by(active=True).order_by(User.name).all()
        except Exception:
            users = []
        return {
            "all_users": users,
            "active_identity": current_identity(),
            "active_user": current_user(),
            "today": date.today(),
        }


# ---------------------------------------------------------------------------
# Routen
# ---------------------------------------------------------------------------


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        ident = current_identity()
        if ident == "admin":
            return redirect(url_for("admin"))
        user = current_user()
        if user:
            return redirect(url_for("user_dashboard", user_id=user.id))
        users = User.query.filter_by(active=True).order_by(User.name).all()
        return render_template("index.html", users=users)

    @app.post("/switch")
    def switch():
        target = request.form.get("identity", "")
        if target == "admin":
            session["identity"] = "admin"
            return redirect(url_for("admin"))
        if target.startswith("user:"):
            try:
                uid = int(target.split(":", 1)[1])
            except ValueError:
                abort(400)
            user = db.session.get(User, uid)
            if not user or not user.active:
                abort(404)
            session["identity"] = f"user:{uid}"
            return redirect(url_for("user_dashboard", user_id=uid))
        if target == "":
            session.pop("identity", None)
            return redirect(url_for("index"))
        abort(400)

    # ----- User-Flows -----

    def _ensure_self(user_id: int) -> User:
        """Stellt sicher, dass die Session zu user_id gehört (oder Admin)."""
        ident = current_identity()
        if ident == "admin":
            user = db.session.get(User, user_id)
            if not user:
                abort(404)
            return user
        if ident == f"user:{user_id}":
            user = db.session.get(User, user_id)
            if not user:
                abort(404)
            return user
        abort(403)

    @app.route("/user/<int:user_id>")
    def user_dashboard(user_id: int):
        user = _ensure_self(user_id)
        try:
            year = int(request.args.get("year", date.today().year))
            month = int(request.args.get("month", date.today().month))
        except ValueError:
            year, month = date.today().year, date.today().month
        if not (1 <= month <= 12):
            year, month = date.today().year, date.today().month

        start = date(year, month, 1)
        if month == 12:
            end_exclusive = date(year + 1, 1, 1)
        else:
            end_exclusive = date(year, month + 1, 1)

        workdays = (
            WorkDay.query.filter(
                WorkDay.user_id == user.id,
                WorkDay.date >= start,
                WorkDay.date < end_exclusive,
            )
            .order_by(WorkDay.date)
            .all()
        )
        absences = (
            Absence.query.filter(
                Absence.user_id == user.id,
                Absence.date >= start,
                Absence.date < end_exclusive,
            )
            .order_by(Absence.date)
            .all()
        )

        summary = logic.build_month_summary(user, year, month, workdays, absences)

        year_workdays = WorkDay.query.filter(
            WorkDay.user_id == user.id,
            WorkDay.date >= date(year, 1, 1),
            WorkDay.date < date(year + 1, 1, 1),
        ).all()
        year_absences = Absence.query.filter(
            Absence.user_id == user.id,
            Absence.date >= date(year, 1, 1),
            Absence.date < date(year + 1, 1, 1),
        ).all()
        year_summary = logic.build_year_summary(
            user, year, year_workdays, year_absences
        )

        prev_year, prev_month = logic.shift_month(year, month, -1)
        next_year, next_month = logic.shift_month(year, month, +1)

        return render_template(
            "user_dashboard.html",
            user=user,
            summary=summary,
            year_summary=year_summary,
            year=year,
            month=month,
            prev_year=prev_year,
            prev_month=prev_month,
            next_year=next_year,
            next_month=next_month,
        )

    @app.route("/user/<int:user_id>/entry", methods=["GET", "POST"])
    def entry_form(user_id: int):
        user = _ensure_self(user_id)
        prefill_date = request.args.get("date") or request.form.get("date")

        if request.method == "POST":
            kind = request.form.get("kind", "work")
            date_str = request.form.get("date", "").strip()
            try:
                entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Ungültiges Datum.", "danger")
                return render_template(
                    "entry_form.html", user=user, prefill_date=prefill_date
                )

            existing_wd = WorkDay.query.filter_by(
                user_id=user.id, date=entry_date
            ).first()
            existing_abs = Absence.query.filter_by(
                user_id=user.id, date=entry_date
            ).first()

            if kind == "work":
                start_str = request.form.get("start_time", "").strip()
                end_str = request.form.get("end_time", "").strip()
                try:
                    start_t = datetime.strptime(start_str, "%H:%M").time()
                    end_t = datetime.strptime(end_str, "%H:%M").time()
                except ValueError:
                    flash("Bitte gültige Start- und Endzeit angeben.", "danger")
                    return render_template(
                        "entry_form.html", user=user, prefill_date=prefill_date
                    )
                if end_t <= start_t:
                    flash("Endzeit muss nach Startzeit liegen.", "danger")
                    return render_template(
                        "entry_form.html", user=user, prefill_date=prefill_date
                    )

                if existing_abs:
                    db.session.delete(existing_abs)
                if existing_wd:
                    existing_wd.start_time = start_t
                    existing_wd.end_time = end_t
                else:
                    db.session.add(
                        WorkDay(
                            user_id=user.id,
                            date=entry_date,
                            start_time=start_t,
                            end_time=end_t,
                        )
                    )
                db.session.commit()
                flash(f"Arbeitszeit für {entry_date.isoformat()} gespeichert.", "success")

            elif kind in (Absence.KIND_VACATION, Absence.KIND_SICK):
                if existing_wd:
                    db.session.delete(existing_wd)
                if existing_abs:
                    existing_abs.kind = kind
                else:
                    db.session.add(
                        Absence(user_id=user.id, date=entry_date, kind=kind)
                    )
                db.session.commit()
                label = "Urlaub" if kind == Absence.KIND_VACATION else "Krankheit"
                flash(
                    f"{label} für {entry_date.isoformat()} gespeichert.", "success"
                )
            else:
                flash("Unbekannter Eintragstyp.", "danger")
                return render_template(
                    "entry_form.html", user=user, prefill_date=prefill_date
                )

            return redirect(
                url_for(
                    "user_dashboard",
                    user_id=user.id,
                    year=entry_date.year,
                    month=entry_date.month,
                )
            )

        return render_template("entry_form.html", user=user, prefill_date=prefill_date)

    @app.route("/user/<int:user_id>/bulk-entry", methods=["GET", "POST"])
    def bulk_entry_form(user_id: int):
        user = _ensure_self(user_id)

        # Feiertage der aktuell relevanten Jahre vorbereiten (Anzeige im Formular).
        today = date.today()
        years = {today.year, today.year - 1, today.year + 1}
        holidays_map: dict[str, str] = {}
        for y in years:
            for d, name in logic.holidays_sachsen_anhalt(y).items():
                holidays_map[d.isoformat()] = name

        if request.method == "POST":
            kind = request.form.get("kind", "work")
            dates_raw = request.form.get("dates", "")

            tokens = [s for s in re.split(r"[,\s;]+", dates_raw) if s]
            parsed_dates: list[date] = []
            for s in tokens:
                try:
                    parsed_dates.append(datetime.strptime(s, "%Y-%m-%d").date())
                except ValueError:
                    flash(f"Ungültiges Datum: {s}", "danger")
                    return render_template(
                        "bulk_entry_form.html",
                        user=user,
                        holidays_json=json.dumps(holidays_map),
                    )

            unique_dates = sorted(set(parsed_dates))
            if not unique_dates:
                flash("Bitte mindestens ein Datum auswählen.", "danger")
                return render_template(
                    "bulk_entry_form.html",
                    user=user,
                    holidays_json=json.dumps(holidays_map),
                )

            if kind == "work":
                start_str = request.form.get("start_time", "").strip()
                end_str = request.form.get("end_time", "").strip()
                try:
                    start_t = datetime.strptime(start_str, "%H:%M").time()
                    end_t = datetime.strptime(end_str, "%H:%M").time()
                except ValueError:
                    flash("Bitte gültige Start- und Endzeit angeben.", "danger")
                    return render_template(
                        "bulk_entry_form.html",
                        user=user,
                        holidays_json=json.dumps(holidays_map),
                    )
                if end_t <= start_t:
                    flash("Endzeit muss nach Startzeit liegen.", "danger")
                    return render_template(
                        "bulk_entry_form.html",
                        user=user,
                        holidays_json=json.dumps(holidays_map),
                    )

                for d in unique_dates:
                    existing_abs = Absence.query.filter_by(
                        user_id=user.id, date=d
                    ).first()
                    if existing_abs:
                        db.session.delete(existing_abs)
                    existing_wd = WorkDay.query.filter_by(
                        user_id=user.id, date=d
                    ).first()
                    if existing_wd:
                        existing_wd.start_time = start_t
                        existing_wd.end_time = end_t
                    else:
                        db.session.add(
                            WorkDay(
                                user_id=user.id,
                                date=d,
                                start_time=start_t,
                                end_time=end_t,
                            )
                        )
                db.session.commit()
                flash(
                    f"Arbeitszeit für {len(unique_dates)} Tag(e) gespeichert.",
                    "success",
                )

            elif kind in (Absence.KIND_VACATION, Absence.KIND_SICK):
                for d in unique_dates:
                    existing_wd = WorkDay.query.filter_by(
                        user_id=user.id, date=d
                    ).first()
                    if existing_wd:
                        db.session.delete(existing_wd)
                    existing_abs = Absence.query.filter_by(
                        user_id=user.id, date=d
                    ).first()
                    if existing_abs:
                        existing_abs.kind = kind
                    else:
                        db.session.add(
                            Absence(user_id=user.id, date=d, kind=kind)
                        )
                db.session.commit()
                label = "Urlaub" if kind == Absence.KIND_VACATION else "Krankheit"
                flash(
                    f"{label} für {len(unique_dates)} Tag(e) gespeichert.",
                    "success",
                )
            else:
                flash("Unbekannter Eintragstyp.", "danger")
                return render_template(
                    "bulk_entry_form.html",
                    user=user,
                    holidays_json=json.dumps(holidays_map),
                )

            first = unique_dates[0]
            return redirect(
                url_for(
                    "user_dashboard",
                    user_id=user.id,
                    year=first.year,
                    month=first.month,
                )
            )

        return render_template(
            "bulk_entry_form.html",
            user=user,
            holidays_json=json.dumps(holidays_map),
        )

    @app.post("/user/<int:user_id>/day/<iso_date>/delete")
    def delete_day(user_id: int, iso_date: str):
        user = _ensure_self(user_id)
        try:
            d = datetime.strptime(iso_date, "%Y-%m-%d").date()
        except ValueError:
            abort(400)
        WorkDay.query.filter_by(user_id=user.id, date=d).delete()
        Absence.query.filter_by(user_id=user.id, date=d).delete()
        db.session.commit()
        flash(f"Eintrag für {d.isoformat()} entfernt.", "info")
        return redirect(
            url_for("user_dashboard", user_id=user.id, year=d.year, month=d.month)
        )

    # ----- Admin-Flows -----

    @app.route("/admin")
    @require_identity("admin")
    def admin():
        users = User.query.order_by(User.name).all()
        today = date.today()
        rows = []
        for u in users:
            year, month = today.year, today.month
            start = date(year, month, 1)
            if month == 12:
                end_exclusive = date(year + 1, 1, 1)
            else:
                end_exclusive = date(year, month + 1, 1)
            workdays = WorkDay.query.filter(
                WorkDay.user_id == u.id,
                WorkDay.date >= start,
                WorkDay.date < end_exclusive,
            ).all()
            absences = Absence.query.filter(
                Absence.user_id == u.id,
                Absence.date >= start,
                Absence.date < end_exclusive,
            ).all()
            summary = logic.build_month_summary(u, year, month, workdays, absences)
            rows.append({"user": u, "summary": summary})
        return render_template("admin.html", rows=rows, year=today.year, month=today.month)

    @app.post("/admin/users")
    @require_identity("admin")
    def admin_create_user():
        name = (request.form.get("name") or "").strip()
        try:
            weekly_hours = float(request.form.get("weekly_hours", "40").replace(",", "."))
        except ValueError:
            flash("Ungültige Wochenstunden.", "danger")
            return redirect(url_for("admin"))
        if not name:
            flash("Name darf nicht leer sein.", "danger")
            return redirect(url_for("admin"))
        if weekly_hours <= 0 or weekly_hours > 60:
            flash("Wochenstunden müssen zwischen 0 und 60 liegen.", "danger")
            return redirect(url_for("admin"))
        if User.query.filter_by(name=name).first():
            flash("Eine Nutzerin mit diesem Namen existiert bereits.", "warning")
            return redirect(url_for("admin"))
        db.session.add(User(name=name, weekly_hours=weekly_hours, active=True))
        db.session.commit()
        flash(f"Nutzerin „{name}“ angelegt.", "success")
        return redirect(url_for("admin"))

    @app.post("/admin/users/<int:user_id>")
    @require_identity("admin")
    def admin_update_user(user_id: int):
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        action = request.form.get("action", "update")
        if action == "deactivate":
            user.active = False
        elif action == "activate":
            user.active = True
        else:
            try:
                weekly_hours = float(
                    request.form.get("weekly_hours", str(user.weekly_hours)).replace(",", ".")
                )
            except ValueError:
                flash("Ungültige Wochenstunden.", "danger")
                return redirect(url_for("admin"))
            if weekly_hours <= 0 or weekly_hours > 60:
                flash("Wochenstunden müssen zwischen 0 und 60 liegen.", "danger")
                return redirect(url_for("admin"))
            user.weekly_hours = weekly_hours
        db.session.commit()
        flash(f"Nutzerin „{user.name}“ aktualisiert.", "success")
        return redirect(url_for("admin"))


# ---------------------------------------------------------------------------
# Wartung: Namen anonymisieren
# ---------------------------------------------------------------------------


def anonymize_user_names(prefix: str = "Nutzerin") -> int:
    """Anonymisiert die Namen aller Nutzerinnen in der DB.

    Jeder User-Name wird durch ``f"{prefix} {n}"`` ersetzt (n = 1, 2, ...),
    geordnet nach ``User.id`` für eine stabile, reproduzierbare Zuordnung.

    Es werden ausschließlich die Namen verändert. ``weekly_hours``, ``active``,
    IDs und sämtliche ``WorkDay``- bzw. ``Absence``-Einträge bleiben unberührt –
    diese referenzieren ohnehin nur ``user_id`` und sind damit von der
    Umbenennung nicht betroffen.

    Da ``User.name`` ein UNIQUE-Constraint hat, läuft die Umbenennung in zwei
    Phasen: zuerst werden alle Namen auf eindeutige Temporärwerte gesetzt und
    geflusht, anschließend wird der finale Name vergeben. So treten keine
    Constraint-Kollisionen auf, selbst wenn Zielnamen bereits vergeben sind.

    Aufruf muss innerhalb eines Flask-App-Kontextes erfolgen.

    :param prefix: Wortteil vor der laufenden Nummer (Default: ``"Nutzerin"``).
    :return: Anzahl umbenannter Nutzerinnen.
    """
    users = User.query.order_by(User.id).all()
    if not users:
        return 0
    for u in users:
        u.name = f"__anon_tmp_{u.id}__"
    db.session.flush()
    for idx, u in enumerate(users, start=1):
        u.name = f"{prefix} {idx}"
    db.session.commit()
    return len(users)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_cmd():
        """Legt die Datenbank-Tabellen an (ohne Daten anzulegen)."""
        with app.app_context():
            db.create_all()
            print("Datenbank initialisiert.")

    @app.cli.command("reset-db")
    def reset_db_cmd():
        """Löscht alle Tabellen und legt sie leer neu an."""
        with app.app_context():
            db.drop_all()
            db.create_all()
            print("Datenbank zurückgesetzt (alle Nutzerinnen + Einträge entfernt).")

    @app.cli.command("anonymize-names")
    @click.option(
        "--prefix",
        default="Nutzerin",
        show_default=True,
        help="Wortteil vor der laufenden Nummer.",
    )
    @click.option(
        "--yes",
        is_flag=True,
        help="Sicherheitsabfrage überspringen (z. B. für Skripte).",
    )
    def anonymize_names_cmd(prefix: str, yes: bool):
        """Anonymisiert die Namen aller Nutzerinnen.

        Vergibt der Reihe nach '<prefix> 1', '<prefix> 2', ... als neue Namen.
        Stunden, Aktiv-Status, Zeit- und Abwesenheits-Einträge bleiben
        unverändert.
        """
        with app.app_context():
            total = User.query.count()
            if total == 0:
                click.echo("Keine Nutzerinnen vorhanden, nichts zu tun.")
                return
            if not yes:
                click.confirm(
                    f"{total} Nutzerin(nen) werden umbenannt zu "
                    f"'{prefix} 1' .. '{prefix} {total}'. Fortfahren?",
                    abort=True,
                )
            n = anonymize_user_names(prefix=prefix)
            click.echo(f"{n} Nutzerin(nen) anonymisiert.")


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
