# Pausen (`PAUSE`)

Abzug der gesetzlichen Mindestpause nach ArbZG §4 von der eingetragenen
Arbeitszeit eines Tages.

## Begriffe

- **Tagesdauer** – Summe der Dauern aller Zeitfenster eines Tages
  (ein offenes Fenster zählt bis jetzt, → SALDO-7).
- **Pflichtpause** – 30 min bei Tagesdauer über 6 h, 45 min über 9 h, sonst 0.
- **Lücke** – Zeit zwischen dem Ende eines Fensters und dem Anfang des nächsten.
- **Netto** – Tagesdauer minus Pausenabzug.

## Regeln

- **PAUSE-1** – Die Pflichtpause richtet sich nach der Tagesdauer, nicht nach
  einzelnen Zeitfenstern. → ADR-0003
  *(offen: derzeit wird die Pause je Zeitfenster bestimmt)*
- **PAUSE-2** – Lücken von mindestens 15 min gelten als genommene Pause und
  werden auf die Pflichtpause angerechnet. Abgezogen wird nur der Rest:
  `Abzug = max(0, Pflichtpause − Summe der Lücken ≥ 15 min)`. → ADR-0003
  *(offen)*
- **PAUSE-3** – Netto ist nie negativ.

### Beispiele

| Zeitfenster | Tagesdauer | Lücken ≥ 15 min | Abzug | Netto |
| ----------- | ---------- | --------------- | ----- | ----- |
| 09:00–17:30 | 8:30 | – | 0:30 | 8:00 |
| 08:00–13:00, 13:00–18:00 | 10:00 | 0 | 0:45 | 9:15 |
| 08:00–12:00, 12:30–17:00 | 8:30 | 0:30 | 0:00 | 8:30 |
| 08:00–12:00, 12:10–17:00 | 8:50 | 0 (10 min zählt nicht) | 0:30 | 8:20 |
| 07:00–12:00, 12:20–18:00 | 10:40 | 0:20 | 0:25 | 10:15 |
| 08:00–13:00 | 5:00 | – | 0:00 | 5:00 |

## Verweise

- ADRs: 0003
- Tests: `tests/test_logic.py`
