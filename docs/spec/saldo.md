# Soll, Ist und Saldo (`SALDO`)

Wie aus den Einträgen Soll, Ist und Saldo für Monat, Jahr und Gesamt
berechnet werden (Dashboard und Admin-Panel).

## Begriffe

- **Tagessoll** – Stunden, die an einem Tag zu arbeiten sind.
- **Ist** – angerechnete Stunden eines Tages.
- **Saldo** – Ist minus Soll (positiv: Überstunden, negativ: Minusstunden).
- **Startdatum / Übertrag** – optional je Nutzerin; der Übertrag ist der
  Saldo zu Beginn des Startdatums (auch negativ).

## Regeln

### Tagessoll und Ist

- **SALDO-1** – Tagessoll an Mo–Fr = Wochenstunden / 5, unabhängig davon, an
  welchen Tagen die Nutzerin tatsächlich arbeitet. → ADR-0004
- **SALDO-2** – Sa, So und Feiertage haben Tagessoll 0. → ADR-0005
- **SALDO-3** – Ist eines Arbeitstags = Netto nach PAUSE. Arbeit an Tagen mit
  Soll 0 zählt damit komplett als Überstunden. → ADR-0005
- **SALDO-4** – Urlaubs- und Krankentage gelten mit dem Tagessoll als erfüllt
  (Ist = Tagessoll).
- **SALDO-5** – Ein leerer Werktag bis einschließlich heute zählt mit vollem
  Soll und Ist 0.

### Zeitlicher Bezug

- **SALDO-6** – In Soll, Ist und Saldo fließen nur Tage bis einschließlich
  heute ein. Einträge an späteren Tagen (z. B. geplanter Urlaub) werden
  angezeigt, zählen aber erst ab ihrem Datum. → ADR-0006
  *(offen: derzeit zählen eingetragene zukünftige Tage bereits mit)*
- **SALDO-7** – Ein offenes Zeitfenster zählt bis zur aktuellen Uhrzeit in
  Ist und Saldo (Live-Wert, Pausenregel inklusive). → ADR-0006
  *(offen: derzeit zählt es erst nach „Ende")*

### Startdatum und Übertrag

- **SALDO-8** – Tage vor dem Startdatum sind inaktiv: Dort vorhandene
  Einträge bleiben gespeichert und sichtbar markiert, zählen aber weder ins
  Soll noch ins Ist. → ADR-0007
- **SALDO-9** – Ein Übertrag ist nur zusammen mit einem Startdatum erlaubt.
  Er fließt in den Monats- und Jahressaldo des Zeitraums ein, in dem das
  Startdatum liegt.

### Zeiträume

- **SALDO-10** – Monatssaldo = Ist − Soll des Monats (+ Übertrag nach
  SALDO-9). Vormonate fließen nicht ein.
- **SALDO-11** – Firmeneinstellung „Saldo zum Jahreswechsel auf 0 setzen",
  Standard an. → ADR-0008
  - an: Der Jahressaldo beginnt am 1.1. (bzw. am Startdatum) bei 0
    (+ Übertrag nach SALDO-9).
  - aus: Der Jahressaldo enthält zusätzlich die Salden aller Vorjahre, ab dem
    Jahr des Startdatums, ohne Startdatum ab dem 1.1. des Jahres mit dem
    ersten Eintrag.
- **SALDO-12** – Der Gesamtsaldo (Dashboard, Admin-Panel) ist der Jahressaldo
  des laufenden Jahres. Angezeigt wird, seit wann er zählt: 1.1. bzw.
  Startdatum bei Nullstellung, sonst der Zählbeginn nach SALDO-11.

## Verweise

- ADRs: 0004, 0005, 0006, 0007, 0008
- Tests: `tests/test_logic.py`, `tests/test_start_date.py`,
  `tests/test_running_total.py`, `tests/test_dashboard.py`
