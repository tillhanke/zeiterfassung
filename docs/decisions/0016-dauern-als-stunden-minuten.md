# 0016 – Dauern werden als Stunden:Minuten angezeigt

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** UI-1

## Kontext

Die App zeigte Dauern und Salden als Dezimalstunden mit Punkt (`7.50 h`,
`+0.25`). Das ist für Nutzerinnen missverständlich: `7.50` wird leicht als
7 Stunden 50 Minuten gelesen. Uhrzeiten werden ohnehin als `HH:MM`
eingegeben und angezeigt.

## Entscheidung

Wir zeigen alle Dauern, Soll-, Ist- und Saldowerte als `h:mm` an, auf volle
Minuten gerundet, Uhrzeiten im 24-Stunden-Format. Salden tragen immer ein
Vorzeichen. Intern rechnet die App weiter mit Dezimalstunden; nur die
Anzeige ändert sich.

## Alternativen

- **Dezimalstunden mit Komma** (`7,75 h`) – in der Lohnbuchhaltung üblich,
  aber im Alltag schwerer mit Uhrzeiten abzugleichen.
- **Beibehalten** (`7.50 h`) – kein deutsches Zahlenformat, missverständlich.

## Konsequenzen

- Anzeige und Live-Vorschau im Formular nutzen dieselbe Formatierung.
- Ein künftiger Export für die Lohnbuchhaltung braucht ggf. zusätzlich
  Dezimalstunden.
