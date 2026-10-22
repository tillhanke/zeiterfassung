# 0003 – Pausenabzug nach Tagessumme mit Anrechnung von Lücken

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** PAUSE-1, PAUSE-2

## Kontext

Seit mehrere Zeitfenster pro Tag möglich sind (2026-10-20), wurde die
gesetzliche Pause je Fenster bestimmt: Zwei Fenster à 5 h direkt
hintereinander ergaben 10 h ohne jeden Abzug. ArbZG §4 bezieht sich aber auf
die Arbeitszeit des Tages und lässt nur Unterbrechungen ab 15 min als Pause
gelten.

## Entscheidung

Wir bestimmen die Pflichtpause (30 min über 6 h, 45 min über 9 h) aus der
Summe aller Fenster eines Tages. Lücken zwischen Fenstern von mindestens
15 min werden als genommene Pause angerechnet; abgezogen wird nur, was dann
noch fehlt.

## Alternativen

- **Pause je Fenster (bisher)** – erlaubt, die Pflichtpause durch Aufteilen
  in Fenster zu umgehen; nicht gesetzeskonform.
- **Nur Tagessumme ohne Lücken** – zieht doppelt ab, wenn die Pause bereits
  als Lücke eingetragen ist.

## Konsequenzen

- Salden von Tagen mit mehreren Fenstern ändern sich rückwirkend.
- Die Live-Vorschau im Formular muss dieselbe Regel anwenden.
