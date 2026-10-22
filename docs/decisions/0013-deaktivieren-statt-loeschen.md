# 0013 – Nutzerinnen deaktivieren statt löschen

- **Status:** Akzeptiert
- **Datum:** 2026-05-05
- **Betrifft:** NUTZ-6

## Kontext

Nutzerinnen verlassen den Betrieb. Ihre Arbeitszeitnachweise müssen aber
aufbewahrt werden und nachvollziehbar bleiben.

## Entscheidung

Das Admin-Panel bietet nur Deaktivieren und Aktivieren an, kein Löschen.
Deaktivierte Nutzerinnen sind nicht mehr auswählbar, ihre Daten bleiben.

## Alternativen

- **Löschen** – Datenverlust, nicht umkehrbar.

## Konsequenzen

- Namen bleiben eindeutig, auch gegenüber deaktivierten Nutzerinnen.
- Für Weitergabe oder Tests gibt es stattdessen `anonymize-names`.
