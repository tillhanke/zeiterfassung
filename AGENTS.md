# AGENTS.md

Anleitung für Coding-Agenten (Claude Code, Cursor, …) in diesem Repository.
Details zu Bedienung und Deployment stehen in der [README](README.md).

## Projekt

Flask-Webapp zur Zeiterfassung für mehrere Nutzerinnen: Arbeitszeiten,
Urlaub/Krank, Pausenabzug nach ArbZG §4, Monats-/Jahressaldo, Admin-Panel.
Bewusst ohne echte Authentifizierung.

- `app.py` – Routen, Session-Handling, CLI-Befehle
- `logic.py` – Geschäftslogik (Pausen, Feiertage, Soll/Ist/Saldo); möglichst frei von Flask
- `models.py` – SQLAlchemy-Modelle
- `migrations/` – Alembic-Migrationen (Flask-Migrate); jede Modelländerung braucht ein Skript
- `templates/` – Jinja-Templates, Vanilla JS
- `tests/` – pytest, ein Modul pro Feature-Bereich

## Befehle

```bash
source .venv/bin/activate
pytest                          # komplette Suite, < 2 s
flask --app app run --debug     # Dev-Server
flask --app app init-db         # Tabellen anlegen/migrieren (idempotent)
flask --app app db migrate -m … # Migrationsskript nach Modelländerung erzeugen
```

## Arbeitsregeln

- Wenn du Funktionalität hinzufügst, schreibe einen Test dafür.
- Wenn du Teile der App geändert hast, lass die Testsuite laufen.
- Teste das Deployment (Docker, systemd) nur, wenn du es geändert hast.
- Prüfe Python-Umgebung oder -Verfügbarkeit nur, wenn du sie geändert hast.
- Nachdem du Funktionalität hinzugefügt oder geändert hast, erstelle einen Git-Commit.

## Konventionen

- UI-Texte, Doku und Commit-Messages auf Deutsch; Personenbezeichnungen im
  generischen Femininum („Nutzerin", „Nutzerinnen").
- Commits im Conventional-Commits-Stil: `feat(bereich): Beschreibung`, `fix: …`, `docs: …`.
- Feature-Branches: `feature/<kurzer-deutscher-name>`.
- Keine Selbsttest-`assert`s auf Modulebene; Prüfungen gehören nach `tests/`.

## Spezifikation und Entscheidungen

Bevor du Verhalten änderst, lies die passenden Dokumente:

- [`docs/spec/`](docs/spec/README.md) – **was** das System tut: aktuelles,
  verbindliches Verhalten als nummerierte Regeln (z. B. `SALDO-3`).
- [`docs/decisions/`](docs/decisions/README.md) – **warum** es so ist:
  Architecture Decision Records (ADRs), unveränderlich.
- [`docs/backlog.md`](docs/backlog.md) – beschlossene, noch offene Änderungen.
  Spec-Regeln mit `*(offen: …)*` sind beschlossen, aber noch nicht umgesetzt.
  Der Code verhält sich dort noch anders, das ist kein Fehler.

Regeln:

1. Eine Verhaltensänderung aktualisiert die betroffene Spec **im selben Commit**
   wie Code und Tests.
2. Tests, die eine Spec-Regel absichern, nennen deren ID im Docstring.
3. Widerspricht eine Änderung einer Spec-Regel oder einem akzeptierten ADR,
   halte an und frage nach, statt die Regel stillschweigend zu ändern.
4. Neue Entscheidungen mit echten Alternativen bekommen ein ADR
   (Status `Vorgeschlagen`, bis es ausdrücklich bestätigt ist).
