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

    # Anzeigeformate (UI-1, UI-2): Dauern als h:mm, Daten deutsch.
    app.add_template_filter(logic.format_hm, "hm")
    app.add_template_filter(lambda h: logic.format_hm(h, signed=True), "hm_signed")
    app.add_template_filter(logic.format_number, "zahl")
    app.add_template_filter(logic.format_date, "datum")
    app.add_template_filter(logic.format_day, "tag")
    app.add_template_filter(logic.format_long_date, "langdatum")


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
    try:
        balance = logic.parse_hours(form.get("start_balance") or "")
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
            f"Vor dem Startdatum ({logic.format_date(user.start_date)}) "
            "können keine Einträge gemacht werden."
        )
    return None


# ---------------------------------------------------------------------------
# Routen
# ---------------------------------------------------------------------------


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        # Immer die Namensauswahl, auch mit aktiver Identität (UI-3): am
        # gemeinsamen Gerät führt „Zeiterfassung“ oben links zurück zur Auswahl.
        users = User.query.filter_by(active=True).order_by(User.name).all()
        # Wer gerade eingestempelt ist, zeigt die Kachel an (UI-3).
        running = {
            wd.user_id: wd.start_time
            for wd in WorkDay.query.filter_by(date=date.today(), end_time=None)
        }
        return render_template("index.html", users=users, running=running)

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

    def _today_summary(user: User, shown: logic.MonthSummary) -> logic.DaySummary:
        """Tageszusammenfassung für heute, auch wenn ein anderer Monat angezeigt wird."""
        today = date.today()
        if (shown.year, shown.month) != (today.year, today.month):
            workdays = WorkDay.query.filter_by(user_id=user.id, date=today).all()
            absences = Absence.query.filter_by(user_id=user.id, date=today).all()
            shown = logic.build_month_summary(
                user, today.year, today.month, workdays, absences
            )
        return next(d for d in shown.days if d.date == today)

    def _clock_block_reason(user: User, today_day: logic.DaySummary) -> Optional[str]:
        """Warum heute nicht gestempelt werden kann (None = Stempeln möglich)."""
        if current_identity() == "admin":
            return (
                "Stempeln kann nur die Nutzerin selbst. "
                "Als Admin kannst du Einträge über „Ändern“ korrigieren."
            )
        if today_day.kind == "holiday":
            return f"Heute ist Feiertag ({today_day.note})." if today_day.note else "Heute ist Feiertag."
        if today_day.kind == "vacation":
            return "Für heute ist Urlaub eingetragen."
        if today_day.kind == "sick":
            return "Für heute ist Krank eingetragen."
        return before_start_error(user, today_day.date)

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

        today_day = _today_summary(user, summary)
        # Offenes Zeitfenster von einem früheren Tag: blockiert das Stempeln
        # (ERF-12), deshalb oben als Hinweis zum Nachtragen (UI-7).
        stale_open = (
            WorkDay.query.filter(
                WorkDay.user_id == user.id,
                WorkDay.date < date.today(),
                WorkDay.end_time.is_(None),
            )
            .order_by(WorkDay.date)
            .first()
        )
        clock_block = _clock_block_reason(user, today_day)
        if stale_open and not clock_block:
            clock_block = (
                f"Erst die fehlende Endzeit vom {logic.format_day(stale_open.date)} "
                "nachtragen, dann ist Einstempeln wieder möglich."
            )

        return render_template(
            "user_dashboard.html",
            user=user,
            today_day=today_day,
            stale_open=stale_open,
            clock_block=clock_block,
            is_admin=current_identity() == "admin",
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

    # ----- Eintragen: ein Formular für einen oder mehrere Tage -----

    def _render_entry_form(
        user: User,
        dates: list[str],
        kind: str = "work",
        windows: Optional[list[tuple[str, str]]] = None,
        editing: bool = False,
    ):
        """Eintragsformular mit Kalender. Liefert dem Kalender Feiertage und
        vorhandene Einträge, damit Überschreiben sichtbar ist."""
        today = date.today()
        years = range(today.year - 1, today.year + 2)
        holidays_map = {
            d.isoformat(): name
            for y in years
            for d, name in logic.holidays_sachsen_anhalt(y).items()
        }
        first, last = date(years[0], 1, 1), date(years[-1], 12, 31)
        entries: dict[str, str] = {}
        for wd in WorkDay.query.filter(
            WorkDay.user_id == user.id, WorkDay.date >= first, WorkDay.date <= last
        ):
            entries[wd.date.isoformat()] = "work"
        for ab in Absence.query.filter(
            Absence.user_id == user.id, Absence.date >= first, Absence.date <= last
        ):
            entries[ab.date.isoformat()] = (
                "vacation" if ab.kind == Absence.KIND_VACATION else "sick"
            )
        return render_template(
            "entry_form.html",
            user=user,
            dates=dates,
            kind=kind,
            windows=windows or DEFAULT_WINDOWS,
            holidays_json=json.dumps(holidays_map),
            entries_json=json.dumps(entries),
            last_workday=_last_workday(user, today),
            editing=editing,
        )

    def _last_workday(user: User, before: date) -> Optional[dict]:
        """Letzter abgeschlossener Arbeitstag vor `before` als Vorlage (ERF-16)."""
        latest = (
            db.session.query(db.func.max(WorkDay.date))
            .filter(
                WorkDay.user_id == user.id,
                WorkDay.date < before,
                WorkDay.end_time.isnot(None),
            )
            .scalar()
        )
        if latest is None:
            return None
        rows = (
            WorkDay.query.filter_by(user_id=user.id, date=latest)
            .order_by(WorkDay.start_time)
            .all()
        )
        if any(w.end_time is None for w in rows):
            return None
        return {
            "date": latest,
            "windows": [
                (w.start_time.strftime("%H:%M"), w.end_time.strftime("%H:%M"))
                for w in rows
            ],
        }

    def _tage(n: int, wort: str = "Tag") -> str:
        return f"{n} {wort}" if n == 1 else f"{n} {wort}e"

    def _save_entries(user: User):
        """Speichert Arbeit oder Abwesenheit für einen oder mehrere Tage.

        Ein Tag: Urlaub/Krank am Wochenende wird abgelehnt; mehrere Tage:
        solche Tage werden mit Hinweis übersprungen (ERF-7). Bei einem
        Validierungsfehler wird nichts gespeichert (ERF-10).
        """
        kind = request.form.get("kind", "work")
        # "dates" (Kalender, mehrere) oder "date" (ein Tag, ältere Formulare).
        dates_raw = request.form.get("dates") or request.form.get("date", "")
        tokens = [t for t in re.split(r"[,\s;]+", dates_raw) if t]
        _, raw_windows, _ = parse_windows(request.form)

        def fail(msg: str):
            flash(msg, "danger")
            return _render_entry_form(user, tokens, kind, raw_windows)

        parsed: list[date] = []
        for t in tokens:
            try:
                parsed.append(datetime.strptime(t, "%Y-%m-%d").date())
            except ValueError:
                return fail(f"Ungültiges Datum: {t}")
        unique_dates = sorted(set(parsed))
        if not unique_dates:
            return fail("Bitte mindestens ein Datum auswählen.")
        if user.start_date is not None:
            before = [d for d in unique_dates if d < user.start_date]
            unique_dates = [d for d in unique_dates if d >= user.start_date]
            if not unique_dates:
                return fail(before_start_error(user, before[0]))
            if before:
                flash(f"{_tage(len(before))} vor dem Startdatum übersprungen.", "info")

        def target(n: int) -> str:
            return logic.format_date(unique_dates[0]) if n == 1 else _tage(n)

        if kind == "work":
            windows, _, error = parse_windows(request.form)
            if error:
                return fail(error)
            for d in unique_dates:
                replace_windows(user.id, d, windows)
            db.session.commit()
            flash(f"Arbeitszeit für {target(len(unique_dates))} gespeichert.", "success")

        elif kind in (Absence.KIND_VACATION, Absence.KIND_SICK):
            # Urlaub/Krank gibt es nur an Werktagen; Wochenendtage überspringen.
            absence_dates = [d for d in unique_dates if d.weekday() < 5]
            skipped = len(unique_dates) - len(absence_dates)
            if not absence_dates:
                return fail("Urlaub/Krank kann nur an Werktagen (Mo–Fr) eingetragen werden.")
            for d in absence_dates:
                WorkDay.query.filter_by(user_id=user.id, date=d).delete()
                existing_abs = Absence.query.filter_by(user_id=user.id, date=d).first()
                if existing_abs:
                    existing_abs.kind = kind
                else:
                    db.session.add(Absence(user_id=user.id, date=d, kind=kind))
            db.session.commit()
            label = "Urlaub" if kind == Absence.KIND_VACATION else "Krankheit"
            if len(absence_dates) == 1:
                flash(f"{label} für {logic.format_date(absence_dates[0])} gespeichert.", "success")
            else:
                flash(f"{label} für {_tage(len(absence_dates))} gespeichert.", "success")
            if skipped:
                flash(f"{_tage(skipped, 'Wochenendtag')} übersprungen.", "info")
        else:
            return fail("Unbekannter Eintragstyp.")

        first = unique_dates[0]
        return redirect(
            url_for("user_dashboard", user_id=user.id, year=first.year, month=first.month)
        )

    @app.route("/user/<int:user_id>/entry", methods=["GET", "POST"])
    def entry_form(user_id: int):
        user = _ensure_self(user_id)
        if request.method == "POST":
            return _save_entries(user)

        # ?date=… (z. B. „Ändern“ in der Tagesliste): Tag vorauswählen und
        # vorhandene Zeitfenster bzw. Abwesenheit vorbelegen. Ohne Datum: heute.
        try:
            d = datetime.strptime(request.args.get("date", ""), "%Y-%m-%d").date()
        except ValueError:
            d = date.today()
        kind = "work"
        windows = [
            (
                w.start_time.strftime("%H:%M"),
                w.end_time.strftime("%H:%M") if w.end_time else "",
            )
            for w in WorkDay.query.filter_by(user_id=user.id, date=d)
            .order_by(WorkDay.start_time)
            .all()
        ]
        absence = Absence.query.filter_by(user_id=user.id, date=d).first()
        if absence:
            kind = "vacation" if absence.kind == Absence.KIND_VACATION else "sick"
        return _render_entry_form(
            user, [d.isoformat()], kind, windows, editing=bool(windows or absence)
        )

    @app.route("/user/<int:user_id>/bulk-entry", methods=["GET", "POST"])
    def bulk_entry_form(user_id: int):
        """Früherer Sammeleintrag; jetzt Teil von entry_form."""
        user = _ensure_self(user_id)
        if request.method == "POST":
            return _save_entries(user)
        return redirect(url_for("entry_form", user_id=user.id))

    # ----- Anfang/Ende stempeln (heute, auf 15 min gerundet) -----

    def _redirect_today(user: User):
        today = date.today()
        return redirect(
            url_for("user_dashboard", user_id=user.id, year=today.year, month=today.month)
        )

    def _ensure_can_clock(user_id: int) -> tuple[User, Optional[str]]:
        """Stempeln darf nur die Nutzerin selbst, nicht Admin (NUTZ-10)."""
        user = _ensure_self(user_id)
        if current_identity() == "admin":
            return user, (
                "Als Admin kann nicht gestempelt werden. "
                "Einträge bitte über „Ändern“ korrigieren."
            )
        return user, None

    @app.post("/user/<int:user_id>/clock/start")
    def clock_start(user_id: int):
        user, error = _ensure_can_clock(user_id)
        if error:
            flash(error, "danger")
            return _redirect_today(user)
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
                f"Vom {logic.format_date(other_open.date)} läuft noch ein Zeitfenster – "
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
        user, error = _ensure_can_clock(user_id)
        if error:
            flash(error, "danger")
            return _redirect_today(user)
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
        flash(f"Eintrag für {logic.format_date(d)} entfernt.", "info")
        return redirect(
            url_for("user_dashboard", user_id=user.id, year=d.year, month=d.month)
        )

    # ----- Admin-Flows -----

    def _month_summary(user: User, year: int, month: int) -> logic.MonthSummary:
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        workdays = WorkDay.query.filter(
            WorkDay.user_id == user.id, WorkDay.date >= start, WorkDay.date < end
        ).all()
        absences = Absence.query.filter(
            Absence.user_id == user.id, Absence.date >= start, Absence.date < end
        ).all()
        return logic.build_month_summary(user, year, month, workdays, absences)

    @app.route("/admin")
    @require_identity("admin")
    def admin():
        today = date.today()
        users = User.query.order_by(User.name).all()
        rows = []
        for u in users:
            total, since = running_total(u)
            rows.append({
                "user": u,
                "summary": _month_summary(u, today.year, today.month),
                "total": total,
                "since": since,
            })
        active_rows = [r for r in rows if r["user"].active]
        return render_template(
            "admin.html",
            rows=active_rows,
            inactive_rows=[r for r in rows if not r["user"].active],
            # Summe der Salden aller aktiven Nutzerinnen (NUTZ-12)
            team_total=sum(r["total"] for r in active_rows),
            team_month=sum(r["summary"].saldo for r in active_rows),
            year=today.year,
            month=today.month,
        )

    @app.route("/admin/settings", methods=["GET", "POST"])
    @require_identity("admin")
    def admin_settings():
        if request.method == "POST":
            yearly_reset = request.form.get("yearly_reset") == "1"
            Setting.set_bool(Setting.YEARLY_RESET, yearly_reset)
            db.session.commit()
            flash(
                "Saldo wird zum Jahreswechsel auf 0 gesetzt."
                if yearly_reset
                else "Saldo wird ins neue Jahr übernommen.",
                "success",
            )
            return redirect(url_for("admin_settings"))
        return render_template("admin_settings.html", yearly_reset=yearly_reset_enabled())

    def _parse_weekly_hours(raw: str) -> tuple[Optional[float], Optional[str]]:
        try:
            hours = float(raw.strip().replace(",", "."))
        except ValueError:
            return None, "Ungültige Wochenstunden."
        if hours <= 0 or hours > 60:
            return None, "Wochenstunden müssen zwischen 0 und 60 liegen."
        return hours, None

    @app.post("/admin/users")
    @require_identity("admin")
    def admin_create_user():
        name = (request.form.get("name") or "").strip()
        weekly_hours, error = _parse_weekly_hours(request.form.get("weekly_hours", "40"))
        if not error and not name:
            error = "Name darf nicht leer sein."
        if error:
            flash(error, "danger")
            return redirect(url_for("admin", _anchor="neu"))
        start_date, start_balance, error = parse_start(request.form)
        if error:
            flash(error, "danger")
            return redirect(url_for("admin", _anchor="neu"))
        if User.query.filter_by(name=name).first():
            flash("Eine Nutzerin mit diesem Namen existiert bereits.", "warning")
            return redirect(url_for("admin", _anchor="neu"))
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

    def _render_user_detail(user: User, form: Optional[dict] = None, status: int = 200):
        today = date.today()
        total, since = running_total(user)
        if form is None:
            form = {
                "name": user.name,
                "weekly_hours": logic.format_number(user.weekly_hours),
                "start_date": user.start_date.isoformat() if user.start_date else "",
                "start_balance": (
                    logic.format_hm(user.start_balance, signed=True) if user.start_date else ""
                ),
            }
        return render_template(
            "admin_user.html",
            user=user,
            form=form,
            summary=_month_summary(user, today.year, today.month),
            total=total,
            since=since,
        ), status

    @app.route("/admin/users/<int:user_id>", methods=["GET", "POST"])
    @require_identity("admin")
    def admin_user(user_id: int):
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        if request.method == "GET":
            return _render_user_detail(user)

        action = request.form.get("action", "update")
        if action == "save":
            # Detailseite: alle Stammdaten in einem Formular (NUTZ-5).
            name = (request.form.get("name") or "").strip()
            weekly_hours, error = _parse_weekly_hours(request.form.get("weekly_hours", ""))
            start_date, start_balance, start_error = parse_start(request.form)
            error = error or start_error
            if not error and not name:
                error = "Name darf nicht leer sein."
            if not error and User.query.filter(User.name == name, User.id != user.id).first():
                error = "Eine Nutzerin mit diesem Namen existiert bereits."
            if error:
                flash(error, "danger")
                return _render_user_detail(user, dict(request.form), 400)
            user.name = name
            user.weekly_hours = weekly_hours
            user.start_date = start_date
            user.start_balance = start_balance
            db.session.commit()
            flash(f"Nutzerin „{user.name}“ gespeichert.", "success")
            return redirect(url_for("admin_user", user_id=user.id))

        # Einzelaktionen (Aktivieren/Deaktivieren und ältere Formulare).
        if action == "deactivate":
            user.active = False
        elif action == "activate":
            user.active = True
        elif action == "start":
            start_date, start_balance, error = parse_start(request.form)
            if error:
                flash(error, "danger")
                return redirect(url_for("admin_user", user_id=user.id))
            user.start_date = start_date
            user.start_balance = start_balance
        else:
            weekly_hours, error = _parse_weekly_hours(
                request.form.get("weekly_hours", str(user.weekly_hours))
            )
            if error:
                flash(error, "danger")
                return redirect(url_for("admin_user", user_id=user.id))
            user.weekly_hours = weekly_hours
        db.session.commit()
        if action == "deactivate":
            flash(f"Nutzerin „{user.name}“ deaktiviert. Ihre Daten bleiben erhalten.", "success")
        elif action == "activate":
            flash(f"Nutzerin „{user.name}“ wieder aktiviert.", "success")
        else:
            flash(f"Nutzerin „{user.name}“ aktualisiert.", "success")
        return redirect(url_for("admin_user", user_id=user.id))


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
