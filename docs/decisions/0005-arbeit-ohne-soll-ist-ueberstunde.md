# 0005 – Arbeit an Wochenende und Feiertag zählt als Überstunden

- **Status:** Akzeptiert
- **Datum:** 2026-10-22 (Wochenende seit 2026-10-20)
- **Betrifft:** ERF-6, ERF-7, ERF-12, SALDO-2, SALDO-3

## Kontext

Wochenendarbeit war seit 2026-10-20 eintragbar. Feiertage wurden
uneinheitlich behandelt: Stempeln war gesperrt, Eintragen über das Formular
möglich, und Urlaub/Krank am Feiertag wurde gespeichert, aber still
ignoriert.

## Entscheidung

Tage ohne Soll (Sa, So, Feiertage) werden gleich behandelt: Arbeit ist auf
allen Wegen eintragbar (Formular, Sammeleintrag, Stempeln) und zählt
komplett als Überstunden. Urlaub/Krank ist dort nicht möglich und wird
abgelehnt bzw. im Sammeleintrag mit Hinweis übersprungen.

## Alternativen

- **Feiertage komplett sperren** – würde echte Feiertagsarbeit nicht
  erfassen.
- **Ist-Zustand dokumentieren** – die stille Ignorierung von Urlaub am
  Feiertag verwirrt Nutzerinnen.

## Konsequenzen

- Das Wochensoll bleibt auf Mo–Fr verteilt (ADR-0004).
- Dashboard muss an Feiertagen „Ändern" und Stempeln anbieten.
