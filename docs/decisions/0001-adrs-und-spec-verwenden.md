# 0001 – Spezifikation und Entscheidungen als Markdown im Repository

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** gesamtes Projekt

## Kontext

Das Projekt wächst und wird überwiegend mit Coding-Agenten weiterentwickelt.
Fachregeln (Pausen, Saldo, Übertrag, Feiertage) und frühere Entscheidungen
standen bisher nur verteilt in README, Commit-Messages und Code. Agenten
können so nicht erkennen, welches Verhalten gewollt ist, und „verbessern"
bewusst getroffene Entscheidungen versehentlich.

## Entscheidung

Wir pflegen drei Ebenen als Markdown im Repository:

1. `AGENTS.md` (eingebunden über `CLAUDE.md`): kurze, immer geladene
   Arbeitsanweisungen für Agenten mit Verweisen auf die anderen Dokumente.
2. `docs/spec/`: lebende Spezifikation des aktuellen Verhaltens mit stabilen
   Regel-IDs, auf die Tests verweisen.
3. `docs/decisions/`: ADRs, die das Warum festhalten, unveränderlich nach
   Annahme.

Verhaltensänderungen aktualisieren die Spec im selben Commit.

## Alternativen

- **Spec-Driven-Frameworks (GitHub Spec Kit, OpenSpec, Kiro-Stil)** – für
  ein kleines Ein-Personen-Projekt zu viel Prozess. Kann später auf der
  bestehenden Struktur aufsetzen.
- **Nur README erweitern** – vermischt Bedienung, Verhalten und Begründung;
  wird für Agenten zu groß, um es immer zu laden.
- **Externes Wiki/Tool** – nicht versioniert mit dem Code, für Agenten
  nicht direkt lesbar.

## Konsequenzen

- Jede Verhaltensänderung kostet etwas mehr Schreibarbeit (Spec-Update).
- Bestehende Entscheidungen müssen einmalig nachdokumentiert werden.
- Die bisherige Cursor-Regel `.cursor/rules/tests.mdc` geht in `AGENTS.md`
  auf; Cursor liest `AGENTS.md` direkt.
