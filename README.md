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
- **Sammeleintrag**: Mehrere (auch nicht aufeinanderfolgende) Tage gleichzeitig
  mit derselben Arbeitszeit bzw. als Urlaub/Krank eintragen. Einzeltage hinzufügen
  oder einen Zeitraum (optional nur Mo-Fr, Feiertage überspringen) einlesen.
- Pausenabzug nach ArbZG §4:
  - > 6 h Bruttoarbeit → 30 min Pause abgezogen
  - > 9 h Bruttoarbeit → 45 min Pause abgezogen
- Monatsübersicht pro Nutzerin: Soll / Ist / Saldo, Urlaub- und Krankentage.
- Soll-Stunden = `wochenstunden / 5` für jeden Werktag (Mo-Fr).
- Saldo wird nur bis zum heutigen Tag (inkl.) gezählt: leere Mo-Fr-Tage in der
  Zukunft erzeugen keine Minus-Stunden. Bereits eingetragene Arbeit/Urlaub/Krank
  an zukünftigen Tagen zählen normal mit.
- Urlaubs- und Krankentage werden mit dem Tagessoll als „erfüllt" gewertet.
- Optionales Startdatum mit Übertrag pro Nutzerin: Einträge vor dem
  Startdatum bleiben gespeichert, zählen aber nicht mehr (und neue sind dort
  nicht möglich). Der Übertrag (Über- oder Minusstunden) ist der Saldo zu
  Beginn des Startdatums und fließt in Monats- und Jahressaldo dieses
  Zeitraums ein.
- Firmenweite Einstellung im Admin-Panel: Saldo zum Jahreswechsel auf 0 setzen
  (Standard) oder Über-/Minusstunden ins neue Jahr übernehmen. Ohne
  Startdatum wird dann ab dem 1.1. des Jahres mit dem ersten Eintrag gezählt.
- Aktueller Gesamtsaldo im Dashboard und im Admin-Panel (je nach Einstellung
  seit Jahresbeginn bzw. seit Startdatum).
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

# Runtime-Abhängigkeiten (Flask, Flask-SQLAlchemy, gunicorn):
pip install -r requirements.txt

# Dev-Abhängigkeiten (zusätzlich pytest):
pip install -r requirements-dev.txt

# Datenbank-Tabellen anlegen:
flask --app app init-db

# Entwicklungsserver starten:
flask --app app run --debug

# Datenbank komplett leeren (alle Nutzerinnen + Einträge):
flask --app app reset-db

# Namen aller Nutzerinnen anonymisieren ("Nutzerin 1", "Nutzerin 2", ...);
# Zeit- und Abwesenheits-Einträge bleiben unangetastet:
flask --app app anonymize-names              # mit Sicherheitsabfrage
flask --app app anonymize-names --yes        # ohne Rückfrage
flask --app app anonymize-names --prefix User --yes

# Tests ausführen (sollten nach jeder Änderung grün sein):
pytest
```

Die App ist anschließend unter <http://127.0.0.1:5000> erreichbar.

### Konfiguration

| Variable     | Pflicht in Produktion | Bedeutung                                                                 |
| ------------ | --------------------- | ------------------------------------------------------------------------- |
| `SECRET_KEY` | **ja**                | Flask-Session-Cookie-Schutz. Im Dev-Modus fällt die App auf einen festen, unsicheren Default zurück und ist nur lokal nutzbar. |

In Produktion:

```bash
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

## Deployment

### Docker

```bash
./build.sh    # baut das Image "zeiterfassung"
SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
  ./run.sh    # startet den Container, Port 8000, instance/ als Volume
```

Der Container ruft beim Start automatisch `flask init-db` auf (idempotent).
Die SQLite-Datei landet im gemounteten `./instance`-Verzeichnis auf dem Host.
Ein `HEALTHCHECK` prüft alle 30 s, ob die Index-Route 200 liefert.

### systemd (Linux)

Direkt-Deployment auf einem Server, Port 80 ohne Root via
`CAP_NET_BIND_SERVICE`:

```bash
# Repository auf den Server kopieren (z. B. nach /opt/zeiterfassung), dann:
sudo deploy/install-systemd.sh
```

Das Script

1. legt den System-User `zeiterfassung` an,
2. erstellt `.venv/` mit allen Runtime-Abhängigkeiten,
3. generiert beim Erst-Lauf `/etc/zeiterfassung.env` mit einem zufälligen
   `SECRET_KEY` (`chmod 0640`, owner `root:zeiterfassung`),
4. initialisiert die Datenbank,
5. aktiviert und startet `zeiterfassung.service`.

Das Service-Profil ist gehärtet (`NoNewPrivileges`, `ProtectSystem=strict`,
`ProtectHome`, `PrivateTmp`, `MemoryDenyWriteExecute`, restriktive
`SystemCallFilter` und `RestrictAddressFamilies`); schreibbar ist nur
`<APP_ROOT>/instance`.

Die SQLite-Datenbank wird im Flask-`instance/`-Ordner als `zeiterf.db` abgelegt.

## Bedienung

1. Auf der Startseite oben rechts eine Nutzerin (oder „Admin") aus dem
   Dropdown auswählen.
2. Als Nutzerin: „+ Tag eintragen" → Datum wählen → Typ (Arbeit / Urlaub /
   Krank) → bei Arbeit Start-/Endzeit angeben. Für mehrere Tage in einem Rutsch:
   „+ Mehrere Tage" → beliebige Einzeltage und/oder Zeiträume sammeln, dann
   einmal speichern.
3. Im Dashboard wird der laufende Monat mit allen Tagen, Soll/Ist/Saldo und
   Urlaubs-/Krankentagen angezeigt. Über die Pfeile kann zwischen Monaten
   navigiert werden.
4. Als Admin: Nutzerinnen-Liste mit Monats- und Gesamtsaldo, Wochenstunden
   sowie Startdatum und Übertrag inline bearbeiten, Nutzerinnen anlegen oder
   deaktivieren, Nullstellung zum Jahreswechsel ein-/ausschalten.

## Projektstruktur

```
zeiterf/
├── app.py                 # Flask-App, Routen, Session-Handling, CLI
├── models.py              # SQLAlchemy: User, WorkDay, Absence
├── logic.py               # Pausenabzug, Soll/Ist-Berechnung
├── requirements.txt       # Runtime-Abhängigkeiten
├── requirements-dev.txt   # zusätzlich pytest
├── pytest.ini
├── Dockerfile             # Production-Image
├── .dockerignore
├── docker-entrypoint.sh   # init-db -> gunicorn
├── build.sh / run.sh      # lokale Docker-Workflows
├── deploy/
│   ├── zeiterfassung.service  # systemd-Unit-Template (gehärtet)
│   └── install-systemd.sh     # Provisionierung Linux-Server
├── README.md
├── AGENTS.md              # Arbeitsanweisungen für Coding-Agenten (CLAUDE.md bindet sie ein)
├── docs/
│   ├── spec/              # verbindliches Verhalten, nummerierte Regeln
│   └── decisions/         # ADRs: warum etwas so entschieden wurde
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── user_dashboard.html
│   ├── entry_form.html
│   ├── bulk_entry_form.html
│   └── admin.html
└── tests/
    ├── conftest.py        # gemeinsame pytest-Fixtures
    ├── test_logic.py      # Pausenregel, Feiertage, Monats-/Jahres-Saldo
    ├── test_models.py     # DB-Constraints, Cascade
    ├── test_auth.py       # Session-Switch, Route-Schutz
    ├── test_entry.py      # Einzel-Tageseintrag
    ├── test_bulk_entry.py # Sammeleintrag (mehrere Tage)
    ├── test_dashboard.py  # Dashboard-Rendering
    ├── test_admin.py      # Admin-Panel, User-CRUD
    ├── test_start_date.py # Startdatum und Übertrag
    ├── test_running_total.py # Gesamtsaldo, Nullstellung zum Jahreswechsel
    └── test_cli.py        # init-db / reset-db
```

## Tests

Alle Tests laufen in unter 2 Sekunden mit isolierter In-Test-SQLite-Datei:

```bash
pytest                     # alles
pytest tests/test_logic.py # nur ein Modul
pytest -k bulk             # alle Tests mit "bulk" im Namen
pytest -v                  # mit Test-Namen
```

Die Tests prüfen sowohl die Geschäftslogik (Pausenabzug, Feiertage,
Saldo-Stichtag) als auch das Verhalten der Routen (Berechtigungen,
Validierung, atomare Bulk-Operationen, Überschreib-Logik).

## Spezifikation, Entscheidungen, Backlog

- [`docs/spec/`](docs/spec/README.md) – verbindliches Verhalten als nummerierte Regeln
- [`docs/decisions/`](docs/decisions/README.md) – Architecture Decision Records
- [`docs/backlog.md`](docs/backlog.md) – beschlossene, noch offene Änderungen und Ideen
