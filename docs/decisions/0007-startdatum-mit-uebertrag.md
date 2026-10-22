# 0007 – Startdatum mit Übertrag, frühere Einträge bleiben erhalten

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** ERF-8, SALDO-8, SALDO-9

## Kontext

Nutzerinnen steigen mitten im Jahr ein oder bringen Über-/Minusstunden aus
einer früheren Erfassung mit. Teilweise gibt es bereits ältere,
unvollständige Einträge.

## Entscheidung

Je Nutzerin kann ein Startdatum mit Übertrag gesetzt werden. Tage davor sind
inaktiv: Einträge bleiben gespeichert und sichtbar, zählen aber nicht; neue
sind dort nicht möglich. Der Übertrag gilt als Saldo zu Beginn des
Startdatums.

## Alternativen

- **Alte Einträge löschen** – nicht umkehrbar, wenn das Startdatum später
  korrigiert wird.
- **Übertrag als Korrekturbuchung an einem Tag** – vermischt Übertrag mit
  echter Arbeitszeit.

## Konsequenzen

- Ein Verschieben des Startdatums wirkt rückwirkend und ohne Datenverlust.
- Ein Übertrag ohne Startdatum ist nicht möglich.
