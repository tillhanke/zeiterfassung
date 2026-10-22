# Feiertage (`FEIER`)

Welche Tage als gesetzliche Feiertage gelten. Wirkung auf Soll und
Erfassung: SALDO-2, ERF-6, ERF-7.

## Regeln

- **FEIER-1** – Es gelten die gesetzlichen Feiertage des Bundeslands aus der
  Firmeneinstellung im Admin-Panel, Standard Sachsen-Anhalt. → ADR-0011
  *(offen: derzeit fest Sachsen-Anhalt)*
- **FEIER-2** – Sachsen-Anhalt: Neujahr, Heilige Drei Könige, Karfreitag,
  Ostermontag, Tag der Arbeit, Christi Himmelfahrt, Pfingstmontag, Tag der
  Deutschen Einheit, Reformationstag, 1. und 2. Weihnachtstag. Nicht:
  Fronleichnam, Allerheiligen, Buß- und Bettag, Frauentag.
- **FEIER-3** – Feiertage werden im Dashboard mit Namen angezeigt.

## Verweise

- ADRs: 0011
- Tests: `tests/test_logic.py`
