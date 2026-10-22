# Backlog

Beschlossene, aber noch nicht umgesetzte Änderungen und offene Ideen.
Erledigte Punkte werden entfernt; das Ergebnis steht dann in Spec und ADRs.

## Beschlossen

Reihenfolge = empfohlene Umsetzungsreihenfolge. Schemaänderungen (B-5, B-6,
B-7) laufen über Alembic-Migrationen (ADR-0012).

| ID | Thema | Entscheidung | Spec |
| -- | ----- | ------------ | ---- |
| B-2 | Pausenabzug nach Tagessumme mit Anrechnung von Lücken ≥ 15 min (auch Live-Vorschau) | ADR-0003 | PAUSE-1, PAUSE-2 |
| B-3 | Feiertage wie Wochenende: Arbeit/Stempeln erlauben, Urlaub/Krank ablehnen bzw. überspringen | ADR-0005 | ERF-6, ERF-7, ERF-12 |
| B-4 | Saldo nur bis heute; offenes Fenster live mitzählen | ADR-0006 | SALDO-6, SALDO-7 |
| B-5 | Rundung als Firmeneinstellung (Modus + Raster), Formular-Raster folgt | ADR-0009 | ERF-5, ERF-15 |
| B-6 | Offene Fenster um Mitternacht verwerfen, Tag markieren | ADR-0010 | ERF-14 |
| B-7 | Bundesland als Firmeneinstellung | ADR-0011 | FEIER-1 |
| B-8 | Wochenstunden ab 0, ohne Obergrenze | ADR-0015 | NUTZ-4 |
| B-9 | Selbsttest-Asserts aus `logic.py` nach `tests/test_logic.py` verschieben | AGENTS.md | – |
| B-10 | Bestehende Tests mit Spec-IDs im Docstring versehen | ADR-0001 | alle |
| B-11 | README-Featureliste auf Verweise in die Spec kürzen | ADR-0001 | – |

## Ideen (nicht entschieden)

- Echte Authentifizierung (Login/PIN), siehe ADR-0002
- Urlaubskontingent und Resturlaub
- CSV-/PDF-Export
- Schichten über Mitternacht
