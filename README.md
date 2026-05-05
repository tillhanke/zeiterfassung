# Zeiterfassung (Flask MVP)

Schlanke Webapp zur Zeiterfassung für mehrere Nutzerinnen.
Pausen werden gemäß ArbZG §4 automatisch abgezogen, eine Monatsübersicht
zeigt Soll, Ist und Saldo (Über-/Minderstunden). Urlaub und Krankentage sind
eintragbar. Ein Admin-Panel verwaltet Nutzerinnen und ihre Wochenarbeitszeit.

> Hinweis: Authentifizierung ist bewusst nicht implementiert. Die Trennung
> zwischen Nutzerinnen und Admin erfolgt nur über einen Selektor in der Topbar.

## Features

- Mehrere Nutzerinnen, jeweils mit individueller Wochenarbeitszeit (Standard 40 h).
- Tageseintrag als **Arbeit** (Start- und Endzeit), **Urlaub** oder **Krank**.
- Pausenabzug nach ArbZG §4:
  - > 6 h Bruttoarbeit → 30 min Pause abgezogen
  - > 9 h Bruttoarbeit → 45 min Pause abgezogen
- Monatsübersicht pro Nutzerin: Soll / Ist / Saldo, Urlaub- und Krankentage.
- Soll-Stunden = `wochenstunden / 5` für jeden Werktag (Mo-Fr).
- Urlaubs- und Krankentage werden mit dem Tagessoll als „erfüllt" gewertet.
- Gesetzliche Feiertage in **Sachsen-Anhalt** werden automatisch berücksichtigt
  (an Feiertagen entfällt das Tagessoll, also kein Aufholbedarf nötig):
  Neujahr, Heilige Drei Könige, Karfreitag, Ostermontag, Tag der Arbeit,
  Christi Himmelfahrt, Pfingstmontag, Tag der Deutschen Einheit,
  Reformationstag und beide Weihnachtsfeiertage.
- Admin-Panel: Übersicht aller Nutzerinnen mit aktuellem Monatssaldo,
  Wochenstunden bearbeiten, Nutzerinnen anlegen / deaktivieren / aktivieren.
- Live-Vorschau der Nettoarbeitszeit beim Eintragen (Vanilla JS).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Datenbank-Tabellen anlegen:
flask --app app init-db

# Entwicklungsserver starten:
flask --app app run --debug

# Datenbank komplett leeren (alle Nutzerinnen + Einträge):
flask --app app reset-db
```

Die App ist anschließend unter <http://127.0.0.1:5000> erreichbar.

Die SQLite-Datenbank wird im Flask-`instance/`-Ordner als `zeiterf.db` abgelegt.

## Bedienung

1. Auf der Startseite oben rechts eine Nutzerin (oder „Admin") aus dem
   Dropdown auswählen.
2. Als Nutzerin: „+ Tag eintragen" → Datum wählen → Typ (Arbeit / Urlaub /
   Krank) → bei Arbeit Start-/Endzeit angeben.
3. Im Dashboard wird der laufende Monat mit allen Tagen, Soll/Ist/Saldo und
   Urlaubs-/Krankentagen angezeigt. Über die Pfeile kann zwischen Monaten
   navigiert werden.
4. Als Admin: Nutzerinnen-Liste mit Saldo, Wochenstunden inline bearbeiten,
   Nutzerinnen anlegen oder deaktivieren.

## Projektstruktur

```
zeiterf/
├── app.py            # Flask-App, Routen, Session-Handling, CLI
├── models.py         # SQLAlchemy: User, WorkDay, Absence
├── logic.py          # Pausenabzug, Soll/Ist-Berechnung
├── requirements.txt
├── README.md
└── templates/
    ├── base.html
    ├── index.html
    ├── user_dashboard.html
    ├── entry_form.html
    └── admin.html
```

## Bewusst ausgeklammert

- Echte Authentifizierung (Login mit Passwort).
- Feiertage anderer Bundesländer (aktuell nur Sachsen-Anhalt).
- Urlaubskontingent / Resturlaub.
- CSV/PDF-Export.
- Mehrtages-Urlaubseintrag (aktuell nur tageweise).
- Über-Mitternacht-Schichten (Arbeitstag muss vor 24:00 enden).
