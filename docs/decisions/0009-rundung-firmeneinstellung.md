# 0009 – Rundung beim Stempeln als Firmeneinstellung

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** ERF-5, ERF-15, NUTZ-8

## Kontext

Stempeln rundet seit 2026-10-20 fest symmetrisch auf 15 min. Wie gerundet
wird, ist eine arbeitsrechtliche bzw. betriebliche Vereinbarung und keine
Entscheidung der Software.

## Entscheidung

Rundung wird Firmeneinstellung im Admin-Panel: Raster 5, 10 oder 15 min und
Modus symmetrisch, zugunsten der Nutzerin, zugunsten des Betriebs oder
minutengenau. Standard bleibt symmetrisch/15 min (bisheriges Verhalten).
Das Raster der Uhrzeit-Auswahl im Formular folgt der Einstellung.

## Alternativen

- **Fest symmetrisch/15 min (bisher)** – passt nicht für jeden Betrieb.
- **Nur an/aus** – deckt einseitige Rundungsvereinbarungen nicht ab.

## Konsequenzen

- Bereits gestempelte Zeiten bleiben unverändert; die Einstellung wirkt nur
  auf neue Stempelungen.
