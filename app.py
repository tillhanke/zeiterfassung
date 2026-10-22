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
import time
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Optional

import click
from sqlalchemy import text
from flask import (
    Flask,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import logic
from models import Absence, Setting, User, WorkDay, db


def create_app(test_config: Optional[dict] = None) -> Flask:
    app = Flask(__name__)
    # SECRET_KEY MUSS in Produktion über die Umgebungsvariable gesetzt werden.
    # Der Dev-Fallback ist absichtlich unsicher und wird nur akzeptiert, wenn
    # FLASK_ENV/SECRET_KEY nicht gesetzt sind – siehe Warnung bei Produktion.
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or "dev-secret-key-change-me",
        SQLALCHEMY_DATABASE_URI="sqlite:///zeiterf.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Nach so vielen Sekunden ohne Aktivität geht es zurück zur Willkommensseite.
        IDLE_TIMEOUT_SECONDS=600,
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

    register_idle_timeout(app)
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
# Inaktivitäts-Timeout
# ---------------------------------------------------------------------------

# Toleranz für /timeout: Der Browser meldet Aktivität nur gedrosselt (max. 1x
# pro Minute) bzw. die letzte Anfrage kann minimal nach der letzten Eingabe
# angekommen sein.
IDLE_TOLERANCE_SECONDS = 30


def _epoch() -> float:
    return time.time()


def _idle_seconds() -> Optional[float]:
    last = session.get("last_activity")
    return None if last is None else _epoch() - last


def _logout_idle() -> None:
    session.pop("identity", None)
    session.pop("last_activity", None)
    minutes = round(current_app.config["IDLE_TIMEOUT_SECONDS"] / 60)
    flash(f"Wegen {minutes} Minuten Inaktivität zur Startseite gewechselt.", "info")


def register_idle_timeout(app: Flask) -> None:
    """Server-seitige Absicherung des Timeouts.

    Jede Anfrage mit aktiver Identität zählt als Aktivität. Ist die letzte
    Aktivität länger als IDLE_TIMEOUT_SECONDS her (z. B. Tab im Ruhezustand),
    wird die Identität verworfen und auf die Willkommensseite umgeleitet.
    Der Browser-Teil (base.html) wechselt bei Inaktivität von selbst.
    """

    @app.before_request
    def enforce_idle_timeout():
        if request.endpoint == "static" or not session.get("identity"):
            return None
        idle = _idle_seconds()
        if idle is not None and idle > app.config["IDLE_TIMEOUT_SECONDS"]:
            _logout_idle()
            if request.endpoint == "keepalive":
                return "", 401
            return redirect(url_for("index"))
        # /timeout prüft selbst und darf die Aktivität nicht auffrischen.
        if request.endpoint != "idle_timeout":
            session["last_activity"] = _epoch()
        return None

    @app.post("/keepalive")
    def keepalive():
        if not session.get("identity"):
            return "", 401
        return "", 204

    @app.get("/timeout")
    def idle_timeout():
        # Nur abmelden, wenn auch der Server keine neuere Aktivität kennt –
        # sonst würde ein inaktiver Tab einen parallel aktiven Tab abmelden.
        idle = _idle_seconds()
        limit = app.config["IDLE_TIMEOUT_SECONDS"] - IDLE_TOLERANCE_SECONDS
        if session.get("identity") and (idle is None or idle >= limit):
            _logout_idle()
        return redirect(url_for("index"))


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
            "idle_timeout_seconds": app.config["IDLE_TIMEOUT_SECONDS"],
        }


# ---------------------------------------------------------------------------
# Zeitfenster-Formularfelder
# ---------------------------------------------------------------------------


def _time_values(form, prefix: str) -> list[str]:
    """Uhrzeiten als "HH:MM" aus <prefix>_hour/<prefix>_minute (Auswahllisten
    im Formular) oder alternativ aus einem einzelnen <prefix>_time-Feld."""
    if f"{prefix}_hour" not in form:
        return form.getlist(f"{prefix}_time")
    hours = form.getlist(f"{prefix}_hour")
    minutes = form.getlist(f"{prefix}_minute")
    # Stunde ohne Minute gilt als volle Stunde; Minute ohne Stunde als leer.
    return [f"{h}:{m or '00'}" if h else "" for h, m in zip(hours, minutes)]


def parse_windows(form) -> tuple[list[logic.Window], list[tuple[str, str]], Optional[str]]:
    """Liest die Zeitfenster aus den Feldern start_time/end_time (mehrfach).

    Komplett leere Zeilen werden ignoriert. Gibt (Fenster, Rohwerte, Fehler)
    zurück; die Rohwerte dienen dazu, das Formular nach einem Fehler mit den
    Eingaben der Nutzerin erneut anzuzeigen.
    """
    starts = _time_values(form, "start")
    ends = _time_values(form, "end")
    raw: list[tuple[str, str]] = []
    windows: list[logic.Window] = []
    for start_str, end_str in zip(starts, ends):
        start_str, end_str = start_str.strip(), end_str.strip()
        if not start_str and not end_str:
            continue
        raw.append((start_str, end_str))
        try:
            windows.append(
                (
                    datetime.strptime(start_str, "%H:%M").time(),
                    datetime.strptime(end_str, "%H:%M").time(),
                )
            )
        except ValueError:
            return [], raw, "Bitte gültige Start- und Endzeit angeben."
    if not windows:
        return [], raw, "Bitte gültige Start- und Endzeit angeben."
    error = logic.validate_windows(windows)
    if error:
        return [], raw, error
    return sorted(windows), raw, None


def replace_windows(user_id: int, d: date, windows: list[logic.Window]) -> None:
    """Ersetzt alle Zeitfenster (und eine evtl. Abwesenheit) eines Tages."""
    Absence.query.filter_by(user_id=user_id, date=d).delete()
    WorkDay.query.filter_by(user_id=user_id, date=d).delete()
    for start_t, end_t in windows:
        db.session.add(
            WorkDay(user_id=user_id, date=d, start_time=start_t, end_time=end_t)
        )


DEFAULT_WINDOWS = [("09:00", "17:30")]


def parse_start(form) -> tuple[Optional[date], float, Optional[str]]:
    """Liest Startdatum und Übertrag (Stunden, auch negativ) aus dem Formular.

    Leeres Datum heißt: kein Startdatum, dann muss auch der Übertrag leer/0 sein.
    Gibt (Startdatum, Übertrag, Fehler) zurück.
    """
    date_str = (form.get("start_date") or "").strip()
    balance_str = (form.get("start_balance") or "").strip().replace(",", ".")
    try:
        balance = float(balance_str) if balance_str else 0.0
    except ValueError:
        return None, 0.0, "Ungültiger Übertrag."
    if not date_str:
        if balance:
            return None, 0.0, "Für einen Übertrag bitte ein Startdatum angeben."
        return None, 0.0, None
    try:
        start = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None, 0.0, "Ungültiges Startdatum."
    return start, balance, None


def yearly_reset_enabled() -> bool:
    """Firmen-Einstellung: Saldo zum Jahreswechsel auf 0 setzen (Default: ja)."""
    return Setting.get_bool(Setting.YEARLY_RESET, True)


def year_summary_for(user: User, year: int) -> logic.YearSummary:
    """Jahresübersicht inkl. Vorjahres-Saldo, falls nicht genullt wird."""
    year_start, next_year_start = date(year, 1, 1), date(year + 1, 1, 1)
    workdays = WorkDay.query.filter(
        WorkDay.user_id == user.id,
        WorkDay.date >= year_start,
        WorkDay.date < next_year_start,
    ).all()
    absences = Absence.query.filter(
        Absence.user_id == user.id,
        Absence.date >= year_start,
        Absence.date < next_year_start,
    ).all()
    carry = 0.0
    if not yearly_reset_enabled():
        carry = logic.carry_over_into(
            user,
            year,
            WorkDay.query.filter(WorkDay.user_id == user.id, WorkDay.date < year_start).all(),
            Absence.query.filter(Absence.user_id == user.id, Absence.date < year_start).all(),
        )
    return logic.build_year_summary(user, year, workdays, absences, carry_over=carry)


def running_total(user: User) -> tuple[float, date]:
    """Aktueller Gesamtsaldo und das Datum, ab dem er gezählt wird."""
    this_year = date.today().year
    if yearly_reset_enabled():
        since = date(this_year, 1, 1)
        if user.start_date is not None and user.start_date > since:
            since = user.start_date
    elif user.start_date is not None:
        since = user.start_date
    else:
        # Wie logic.carry_over_into: ab dem 1.1. des Jahres mit dem ersten Eintrag.
        firsts = [
            d
            for d in (
                db.session.query(db.func.min(WorkDay.date)).filter_by(user_id=user.id).scalar(),
                db.session.query(db.func.min(Absence.date)).filter_by(user_id=user.id).scalar(),
            )
            if d is not None
        ]
        since = date(min([this_year] + [d.year for d in firsts]), 1, 1)
    return year_summary_for(user, this_year).saldo, since


def before_start_error(user: User, d: date) -> Optional[str]:
    if user.start_date is not None and d < user.start_date:
        return (
            f"Vor dem Startdatum ({user.start_date.isoformat()}) "
            "können keine Einträge gemacht werden."
        )
    return None


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
        session["last_activity"] = _epoch()
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

        year_summary = year_summary_for(user, year)
        total, total_since = running_total(user)

        prev_year, prev_month = logic.shift_month(year, month, -1)
        next_year, next_month = logic.shift_month(year, month, +1)

        return render_template(
            "user_dashboard.html",
            user=user,
            summary=summary,
            year_summary=year_summary,
            running_total=total,
            running_since=total_since,
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

        def render_form(windows=None):
            return render_template(
                "entry_form.html",
                user=user,
                prefill_date=prefill_date,
                windows=windows or DEFAULT_WINDOWS,
            )

        if request.method == "POST":
            kind = request.form.get("kind", "work")
            date_str = request.form.get("date", "").strip()
            try:
                entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Ungültiges Datum.", "danger")
                return render_form()
            error = before_start_error(user, entry_date)
            if error:
                flash(error, "danger")
                return render_form()

            existing_abs = Absence.query.filter_by(
                user_id=user.id, date=entry_date
            ).first()

            if kind == "work":
                windows, raw, error = parse_windows(request.form)
                if error:
                    flash(error, "danger")
                    return render_form(raw)

                replace_windows(user.id, entry_date, windows)
                db.session.commit()
                flash(f"Arbeitszeit für {entry_date.isoformat()} gespeichert.", "success")

            elif kind in (Absence.KIND_VACATION, Absence.KIND_SICK):
                if entry_date.weekday() >= 5:
                    flash(
                        "Urlaub/Krank kann nur an Werktagen (Mo–Fr) eingetragen werden.",
                        "danger",
                    )
                    return render_form()
                WorkDay.query.filter_by(user_id=user.id, date=entry_date).delete()
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
                return render_form()

            return redirect(
                url_for(
                    "user_dashboard",
                    user_id=user.id,
                    year=entry_date.year,
                    month=entry_date.month,
                )
            )

        # Beim Bearbeiten eines Tages die vorhandenen Zeitfenster vorbelegen.
        existing: list[tuple[str, str]] = []
        if prefill_date:
            try:
                d = datetime.strptime(prefill_date, "%Y-%m-%d").date()
            except ValueError:
                d = None
            if d:
                existing = [
                    (
                        w.start_time.strftime("%H:%M"),
                        w.end_time.strftime("%H:%M") if w.end_time else "",
                    )
                    for w in WorkDay.query.filter_by(user_id=user.id, date=d)
                    .order_by(WorkDay.start_time)
                    .all()
                ]
        return render_form(existing)

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

        def render_form(windows=None):
            return render_template(
                "bulk_entry_form.html",
                user=user,
                holidays_json=json.dumps(holidays_map),
                windows=windows or DEFAULT_WINDOWS,
            )

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
                    return render_form()

            unique_dates = sorted(set(parsed_dates))
            if not unique_dates:
                flash("Bitte mindestens ein Datum auswählen.", "danger")
                return render_form()
            if user.start_date is not None:
                before = [d for d in unique_dates if d < user.start_date]
                unique_dates = [d for d in unique_dates if d >= user.start_date]
                if not unique_dates:
                    flash(before_start_error(user, before[0]), "danger")
                    return render_form()
                if before:
                    flash(f"{len(before)} Tag(e) vor dem Startdatum übersprungen.", "info")

            if kind == "work":
                windows, raw, error = parse_windows(request.form)
                if error:
                    flash(error, "danger")
                    return render_form(raw)

                for d in unique_dates:
                    replace_windows(user.id, d, windows)
                db.session.commit()
                flash(
                    f"Arbeitszeit für {len(unique_dates)} Tag(e) gespeichert.",
                    "success",
                )

            elif kind in (Absence.KIND_VACATION, Absence.KIND_SICK):
                # Urlaub/Krank gibt es nur an Werktagen; Wochenendtage überspringen.
                absence_dates = [d for d in unique_dates if d.weekday() < 5]
                skipped = len(unique_dates) - len(absence_dates)
                if not absence_dates:
                    flash(
                        "Urlaub/Krank kann nur an Werktagen (Mo–Fr) eingetragen werden.",
                        "danger",
                    )
                    return render_form()
                for d in absence_dates:
                    WorkDay.query.filter_by(user_id=user.id, date=d).delete()
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
                    f"{label} für {len(absence_dates)} Tag(e) gespeichert.",
                    "success",
                )
                if skipped:
                    flash(f"{skipped} Wochenendtag(e) übersprungen.", "info")
            else:
                flash("Unbekannter Eintragstyp.", "danger")
                return render_form()

            first = unique_dates[0]
            return redirect(
                url_for(
                    "user_dashboard",
                    user_id=user.id,
                    year=first.year,
                    month=first.month,
                )
            )

        return render_form()

    # ----- Anfang/Ende stempeln (heute, auf 15 min gerundet) -----

    def _redirect_today(user: User):
        today = date.today()
        return redirect(
            url_for("user_dashboard", user_id=user.id, year=today.year, month=today.month)
        )

    @app.post("/user/<int:user_id>/clock/start")
    def clock_start(user_id: int):
        user = _ensure_self(user_id)
        now = datetime.now()
        today = now.date()
        start_t = logic.round_to_quarter(now)

        if logic.is_holiday(today):
            flash("An Feiertagen kann keine Arbeitszeit gestempelt werden.", "danger")
            return _redirect_today(user)
        error = before_start_error(user, today)
        if error:
            flash(error, "danger")
            return _redirect_today(user)
        if Absence.query.filter_by(user_id=user.id, date=today).first():
            flash("Für heute ist Urlaub/Krank eingetragen.", "danger")
            return _redirect_today(user)
        other_open = WorkDay.query.filter(
            WorkDay.user_id == user.id,
            WorkDay.end_time.is_(None),
            WorkDay.date != today,
        ).first()
        if other_open:
            flash(
                f"Vom {other_open.date.isoformat()} läuft noch ein Zeitfenster – "
                "bitte dort zuerst über „Ändern“ eine Endzeit setzen.",
                "danger",
            )
            return _redirect_today(user)

        existing = WorkDay.query.filter_by(user_id=user.id, date=today).all()
        error = logic.check_clock_start(
            [(w.start_time, w.end_time) for w in existing], start_t
        )
        if error:
            flash(error, "danger")
            return _redirect_today(user)

        db.session.add(
            WorkDay(user_id=user.id, date=today, start_time=start_t, end_time=None)
        )
        db.session.commit()
        flash(f"Anfang {start_t:%H:%M} gesetzt.", "success")
        return _redirect_today(user)

    @app.post("/user/<int:user_id>/clock/end")
    def clock_end(user_id: int):
        user = _ensure_self(user_id)
        now = datetime.now()
        today = now.date()
        end_t = logic.round_to_quarter(now)

        running = WorkDay.query.filter_by(
            user_id=user.id, date=today, end_time=None
        ).first()
        if not running:
            flash("Heute läuft kein Zeitfenster.", "warning")
            return _redirect_today(user)
        error = logic.check_clock_end(running.start_time, end_t)
        if error:
            flash(error, "warning")
            return _redirect_today(user)

        running.end_time = end_t
        db.session.commit()
        flash(
            f"Ende {end_t:%H:%M} gesetzt ({running.start_time:%H:%M}–{end_t:%H:%M}).",
            "success",
        )
        return _redirect_today(user)

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
            total, since = running_total(u)
            rows.append({"user": u, "summary": summary, "total": total, "since": since})
        return render_template(
            "admin.html",
            rows=rows,
            year=today.year,
            month=today.month,
            yearly_reset=yearly_reset_enabled(),
        )

    @app.post("/admin/settings")
    @require_identity("admin")
    def admin_settings():
        yearly_reset = request.form.get("yearly_reset") == "1"
        Setting.set_bool(Setting.YEARLY_RESET, yearly_reset)
        db.session.commit()
        flash(
            "Saldo wird zum Jahreswechsel auf 0 gesetzt."
            if yearly_reset
            else "Saldo wird ins neue Jahr übernommen.",
            "success",
        )
        return redirect(url_for("admin"))

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
        start_date, start_balance, error = parse_start(request.form)
        if error:
            flash(error, "danger")
            return redirect(url_for("admin"))
        if User.query.filter_by(name=name).first():
            flash("Eine Nutzerin mit diesem Namen existiert bereits.", "warning")
            return redirect(url_for("admin"))
        db.session.add(
            User(
                name=name,
                weekly_hours=weekly_hours,
                active=True,
                start_date=start_date,
                start_balance=start_balance,
            )
        )
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
        elif action == "start":
            start_date, start_balance, error = parse_start(request.form)
            if error:
                flash(error, "danger")
                return redirect(url_for("admin"))
            user.start_date = start_date
            user.start_balance = start_balance
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
# Schema-Migration
# ---------------------------------------------------------------------------


def migrate_workdays_schema() -> bool:
    """Bringt eine ältere `workdays`-Tabelle auf das aktuelle Schema.

    - UNIQUE(user_id, date) entfällt (mehrere Zeitfenster pro Tag)
    - end_time wird nullable (laufendes Zeitfenster per "Anfang")

    SQLite kann Constraints nicht per ALTER TABLE ändern, daher wird die
    Tabelle neu aufgebaut und die Daten werden übernommen. Idempotent; gibt
    True zurück, wenn migriert wurde.
    """
    ddl = db.session.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='workdays'")
    ).scalar()
    if not ddl:
        return False
    normalized = " ".join(ddl.split())
    if (
        "uq_workday_user_date" not in normalized
        and "end_time TIME NOT NULL" not in normalized
    ):
        return False
    db.session.close()
    # Eine Transaktion: schlägt ein Schritt fehl, bleibt die alte Tabelle intakt.
    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE workdays RENAME TO workdays_old"))
        # Indizes wandern beim RENAME mit und würden den Neuaufbau blockieren.
        conn.execute(text("DROP INDEX IF EXISTS ix_workdays_user_date"))
        WorkDay.__table__.create(conn)
        conn.execute(
            text(
                "INSERT INTO workdays (id, user_id, date, start_time, end_time) "
                "SELECT id, user_id, date, start_time, end_time FROM workdays_old"
            )
        )
        conn.execute(text("DROP TABLE workdays_old"))
    return True


def migrate_users_schema() -> bool:
    """Ergänzt in einer älteren `users`-Tabelle die Spalten für Startdatum und
    Übertrag. Idempotent; gibt True zurück, wenn migriert wurde."""
    columns = {
        row[1] for row in db.session.execute(text("PRAGMA table_info(users)"))
    }
    if not columns:
        return False
    added = False
    if "start_date" not in columns:
        db.session.execute(text("ALTER TABLE users ADD COLUMN start_date DATE"))
        added = True
    if "start_balance" not in columns:
        db.session.execute(
            text("ALTER TABLE users ADD COLUMN start_balance FLOAT NOT NULL DEFAULT 0")
        )
        added = True
    db.session.commit()
    return added


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_cmd():
        """Legt die Datenbank-Tabellen an (ohne Daten anzulegen)."""
        with app.app_context():
            if migrate_workdays_schema():
                print("Tabelle workdays auf aktuelles Schema migriert.")
            if migrate_users_schema():
                print("Tabelle users um Startdatum/Übertrag ergänzt.")
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
