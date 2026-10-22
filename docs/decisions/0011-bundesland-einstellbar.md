# 0011 – Bundesland für Feiertage als Firmeneinstellung

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** FEIER-1

## Kontext

Die Feiertage sind fest für Sachsen-Anhalt im Code berechnet. Die App soll
auch für Betriebe in anderen Bundesländern nutzbar sein.

## Entscheidung

Das Bundesland wird Firmeneinstellung im Admin-Panel, Standard
Sachsen-Anhalt. Die Feiertagsberechnung soll eine etablierte Bibliothek
(z. B. `holidays`) übernehmen, statt alle Länder selbst zu pflegen.

## Alternativen

- **Nur Sachsen-Anhalt (bisher)** – schließt andere Standorte aus.
- **Bundesland je Nutzerin** – genauer bei Pendlerinnen, im Betrieb aber
  nicht nötig.

## Konsequenzen

- Neue Laufzeitabhängigkeit.
- Ein Wechsel des Bundeslands wirkt rückwirkend auf alle Salden.
