# 0006 – Saldo zählt bis jetzt: keine Zukunft, offene Fenster live

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** SALDO-6, SALDO-7

## Kontext

Seit 2026-05-11 erzeugen leere zukünftige Werktage kein Minus; bereits
eingetragene zukünftige Tage (z. B. geplanter Urlaub) zählten aber sofort
mit. Ein gestempeltes, noch offenes Zeitfenster zählte dagegen erst nach
„Ende". Der Saldo zeigte damit weder den Stand von jetzt noch eine
Prognose.

## Entscheidung

Der Saldo zeigt den Stand von jetzt: Nur Tage bis einschließlich heute
zählen, zukünftige Einträge werden angezeigt, zählen aber erst an ihrem
Tag. Ein offenes Zeitfenster zählt bis zur aktuellen Uhrzeit mit, inklusive
Pausenregel.

## Alternativen

- **Zukünftige Einträge mitzählen (bisher)** – verzerrt den aktuellen Saldo
  durch geplanten Urlaub.
- **Volles Monatssoll** – zeigt, was bis Monatsende fehlt, aber nicht den
  aktuellen Stand.
- **Offenes Fenster nur separat anzeigen** – Saldo hinkt während der Arbeit
  hinterher.

## Konsequenzen

- Der Saldo ändert sich während eines laufenden Fensters von Aufruf zu
  Aufruf.
- Geplanter Urlaub wirkt erst an seinem Tag auf den Saldo.
