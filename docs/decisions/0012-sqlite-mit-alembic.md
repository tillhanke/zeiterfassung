# 0012 – SQLite mit Alembic-Migrationen

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** Datenhaltung, `init-db`

## Kontext

Die Daten liegen in einer SQLite-Datei im `instance/`-Ordner. Bisher hat
`init-db` Schemaänderungen mit selbstgeschriebenem Code nachgezogen
(Tabelle neu aufbauen, Spalten ergänzen). Mehrere beschlossene Änderungen
brauchen weitere Schemaänderungen; jede würde neuen Sonderfall-Code
erfordern.

## Entscheidung

SQLite bleibt, weil es für einen Standort mit wenigen Nutzerinnen genügt.
Schemaänderungen laufen künftig über Alembic (Flask-Migrate) als
nummerierte Migrationsskripte, die beim Start bzw. in `init-db` angewendet
werden. Bestehende Datenbanken werden einmalig übernommen.

## Alternativen

- **Eigene Migrationen (bisher)** – wächst mit jeder Änderung und ist
  schwer zu testen.
- **PostgreSQL** – mehr Betriebsaufwand ohne Bedarf.

## Konsequenzen

- Neue Abhängigkeit (Flask-Migrate/Alembic).
- SQLite-Einschränkungen bei `ALTER TABLE` erfordern Alembic-Batch-Mode.
