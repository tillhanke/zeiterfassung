# Spezifikation

Die Spec beschreibt das **aktuelle, verbindliche Verhalten** der App: was
gilt, nicht wie es dazu kam (das steht in den [ADRs](../decisions/README.md)).
Weicht der Code von der Spec ab, ist das ein Fehler, und zwar entweder im
Code oder in der Spec. Er wird bewusst aufgelöst, nicht stillschweigend.

## Aufbau

- Eine Datei pro fachlichem Bereich: `docs/spec/<bereich>.md`
  (z. B. `pausen.md`, `saldo.md`, `eintraege.md`, `admin.md`).
- Jeder Bereich hat ein festes, großgeschriebenes **Kürzel** (z. B. `PAUSE`,
  `SALDO`). Es wird in der Übersicht unten registriert.
- Vorlage: [`_vorlage.md`](_vorlage.md).

## Regeln

Verhalten wird als nummerierte Regeln formuliert:

```markdown
- **SALDO-3** – Leere Werktage nach dem heutigen Tag erzeugen kein Minus.
```

- IDs sind **stabil**: Sie werden nie umnummeriert oder wiederverwendet.
  Neue Regeln bekommen die nächste freie Nummer.
- Entfällt eine Regel, bleibt die ID stehen und wird durchgestrichen
  markiert: `- ~~**SALDO-4**~~ – entfallen, siehe ADR-0007.`
- Eine Regel ist eine prüfbare Aussage. Wo möglich mit konkretem Beispiel
  (Eingabe → Ergebnis).
- Formulierung aus Sicht der Fachlichkeit, nicht der Implementierung
  (keine Funktions- oder Tabellennamen, außer sie sind selbst Teil des Verhaltens).

## Verknüpfung mit Tests und ADRs

- Tests, die eine Regel absichern, nennen die ID im Docstring:
  `"""SALDO-3: zukünftige leere Tage zählen nicht."""`
  Damit findet `grep -rn SALDO-3` Spec, Tests und Code.
- Begründungen stehen nicht in der Spec, sondern im ADR, auf das die Regel
  verweist (`→ ADR-0004`).

## Änderungen

Eine Verhaltensänderung ändert Spec, Code und Tests im selben Commit.

## Bereiche

| Kürzel | Datei | Inhalt |
| ------ | ----- | ------ |
| –      | –     | noch keine Bereiche angelegt |
