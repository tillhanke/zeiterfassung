# Nutzerinnen, Zugang und Verwaltung (`NUTZ`)

Wer die App wie benutzt: Identitätsauswahl ohne Login, Inaktivitäts-Timeout,
Verwaltung der Nutzerinnen und Firmeneinstellungen im Admin-Panel.

## Begriffe

- **Identität** – in der Session gewählte Rolle: eine Nutzerin oder „Admin".
- **Firmeneinstellung** – gilt für alle Nutzerinnen, wird im Admin-Panel gesetzt.

## Regeln

### Zugang

- **NUTZ-1** – Es gibt keinen Login. Die Identität wird auf der Startseite
  aus den aktiven Nutzerinnen und „Verwaltung" (Admin) gewählt; „Abmelden"
  in der Topbar führt zurück dorthin (→ UI-3). → ADR-0002, ADR-0018
- **NUTZ-2** – Als Nutzerin sind nur die eigenen Daten sichtbar und
  änderbar. Als Admin sind alle Nutzerinnen und ihre Dashboards zugänglich.
- **NUTZ-10** – Admin kann Einträge aller Nutzerinnen anlegen, ändern und
  löschen, aber nicht für sie stempeln. „Anfang"/„Ende" als Admin wird mit
  Hinweis abgelehnt, es wird nichts gespeichert. → ADR-0017
- **NUTZ-3** – Nach 10 min ohne Eingabe (Maus, Tastatur, Scrollen, Touch)
  wechselt die Seite zur Startseite und die Identität wird verworfen. Der
  Server setzt das auch durch, wenn der Browser es nicht tut (z. B. nach
  Standby). Ein inaktiver Tab meldet einen parallel aktiven Tab nicht ab.
  → ADR-0002

### Verwaltung

- **NUTZ-4** – Beim Anlegen: Name nicht leer und eindeutig, Wochenstunden
  ≥ 0 ohne Obergrenze (Standard 40), Startdatum und Übertrag optional.
  Wochenstunden 0 bedeutet: kein Soll, jede Arbeit zählt als Überstunden.
  → ADR-0015
  *(offen: derzeit 0 < Wochenstunden ≤ 60)*
- **NUTZ-5** – Wochenstunden, Startdatum und Übertrag sind nachträglich
  änderbar und wirken rückwirkend auf alle Berechnungen.
- **NUTZ-6** – Nutzerinnen werden deaktiviert, nicht gelöscht. Deaktivierte
  erscheinen nicht in der Auswahl, ihre Daten bleiben erhalten, sie können
  wieder aktiviert werden. → ADR-0013
- **NUTZ-7** – Das Admin-Panel zeigt alle Nutzerinnen mit Monatssaldo des
  laufenden Monats und Gesamtsaldo.
- **NUTZ-8** – Firmeneinstellungen: Nullstellung zum Jahreswechsel
  (SALDO-11), Rundung beim Stempeln (ERF-15), Bundesland (FEIER-1).

### Wartung

- **NUTZ-9** – `flask anonymize-names` ersetzt alle Namen durch
  „<Präfix> 1", „<Präfix> 2", … in der Reihenfolge der Anlage. Alle anderen
  Daten bleiben unverändert.

## Verweise

- ADRs: 0002, 0013, 0015, 0017, 0018
- Tests: `tests/test_auth.py`, `tests/test_idle_timeout.py`,
  `tests/test_admin.py`, `tests/test_anonymize.py`, `tests/test_clock.py`
