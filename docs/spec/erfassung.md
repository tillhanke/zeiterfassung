# Erfassung (`ERF`)

Wie Nutzerinnen Arbeitszeiten und Abwesenheiten eintragen: Einzeleintrag,
Sammeleintrag und Stempeln („Anfang"/„Ende") im Dashboard.

## Begriffe

- **Zeitfenster** – zusammenhängende Arbeitszeit eines Tages mit Anfang und
  Ende. Ein Tag kann mehrere Zeitfenster haben.
- **Offenes Zeitfenster** – per „Anfang" gestartet, „Ende" noch nicht gesetzt.
- **Abwesenheit** – Urlaub oder Krank für einen ganzen Tag.
- **Raster** – Minutenschritte für Uhrzeiten (Firmeneinstellung, Standard 15 min).

## Regeln

### Tage und Zeitfenster

- **ERF-1** – Ein Tag einer Nutzerin ist entweder leer, ein Arbeitstag
  (1..n Zeitfenster) oder eine Abwesenheit. Speichern von Arbeit ersetzt eine
  vorhandene Abwesenheit und umgekehrt.
- **ERF-2** – Ein Zeitfenster endet nach seinem Anfang am selben Tag.
  Zeitfenster über Mitternacht gibt es nicht.
- **ERF-3** – Zeitfenster eines Tages dürfen sich berühren, aber nicht
  überschneiden. Beispiel: 08:00–12:00 und 12:00–14:00 ist gültig,
  08:00–12:00 und 11:00–14:00 nicht.
- **ERF-4** – Beim Bearbeiten werden alle Zeitfenster des Tages gemeinsam
  ersetzt. Löschen eines Tages entfernt alle Zeitfenster und die Abwesenheit.
- **ERF-5** – Uhrzeiten werden im Formular als Stunde und Minute im Raster
  gewählt (→ ERF-15). Vorhandene Zeiten außerhalb des Rasters bleiben beim
  Bearbeiten erhalten.
  *(offen: Raster ist derzeit fest 15 min)*

### Wann was eingetragen werden darf

- **ERF-6** – Arbeit kann an jedem Tag eingetragen werden, auch an Sa/So und
  an Feiertagen. → ADR-0005
  *(offen: an Feiertagen bietet das Dashboard derzeit kein „Ändern" an)*
- **ERF-7** – Urlaub/Krank nur an Tagen mit Soll (Mo–Fr ohne Feiertag). Der
  Einzeleintrag lehnt andere Tage ab, der Sammeleintrag überspringt sie mit
  Hinweis. → ADR-0005
  *(offen: an Feiertagen wird Urlaub/Krank derzeit gespeichert und ignoriert)*
- **ERF-8** – Vor dem Startdatum der Nutzerin sind keine Einträge und kein
  Stempeln möglich. Der Sammeleintrag überspringt solche Tage mit Hinweis.
  → ADR-0007

### Sammeleintrag

- **ERF-9** – Der Sammeleintrag trägt beliebig viele, auch nicht
  aufeinanderfolgende Tage mit denselben Zeitfenstern bzw. derselben
  Abwesenheit ein.
- **ERF-10** – Bei einem Validierungsfehler wird kein einziger Tag gespeichert.

### Stempeln

- **ERF-11** – „Anfang" startet für heute ein offenes Zeitfenster mit der
  aktuellen Uhrzeit, gerundet nach ERF-15.
- **ERF-12** – „Anfang" ist nicht möglich, wenn heute Urlaub/Krank eingetragen
  ist, vor dem Startdatum, wenn bereits ein offenes Zeitfenster existiert
  oder wenn der gerundete Anfang vor dem Ende eines vorhandenen Fensters liegt.
  *(offen: an Feiertagen ist Stempeln derzeit gesperrt; das entfällt mit ADR-0005)*
- **ERF-13** – „Ende" setzt die gerundete aktuelle Uhrzeit als Ende des
  offenen Fensters. Liegt sie nicht nach dem Anfang, läuft das Fenster mit
  Hinweis weiter.
- **ERF-14** – Ist ein Zeitfenster am Ende seines Tages (23:59) noch offen,
  wird es gelöscht. Abgeschlossene Fenster desselben Tages bleiben. Der Tag
  wird als „Stempeln unvollständig – bitte nachtragen" markiert, bis die
  Nutzerin ihn bearbeitet oder löscht. Bis dahin zählen fehlende Stunden
  normal ins Minus. → ADR-0010
  *(offen: derzeit bleibt das Fenster offen und blockiert neues Stempeln)*
- **ERF-15** – Gestempelte Zeiten werden nach Firmeneinstellung gerundet:
  Raster 5, 10 oder 15 min (Standard 15) und Modus *symmetrisch* (zur
  nächsten Rasterzeit, Standard), *zugunsten der Nutzerin* (Anfang ab, Ende
  auf), *zugunsten des Betriebs* (Anfang auf, Ende ab) oder *minutengenau*.
  Gerundet wird höchstens bis zur letzten Rasterzeit vor Mitternacht.
  Beispiel symmetrisch/15: 08:07 → 08:00, 08:08 → 08:15, 23:59 → 23:45.
  → ADR-0009
  *(offen: derzeit fest symmetrisch auf 15 min)*

## Nicht im Umfang

- Schichten über Mitternacht (siehe [Backlog](../backlog.md)).

## Verweise

- ADRs: 0005, 0007, 0009, 0010
- Tests: `tests/test_entry.py`, `tests/test_bulk_entry.py`, `tests/test_clock.py`
