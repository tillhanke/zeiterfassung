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
- **SALDO-5** – Ein leerer Werktag bis einschließlich heute zählt mit vollem Soll.
```

- IDs sind **stabil**: Sie werden nie umnummeriert oder wiederverwendet.
  Neue Regeln bekommen die nächste freie Nummer.
- Entfällt eine Regel, bleibt die ID stehen und wird durchgestrichen
  markiert: `- ~~**SALDO-4**~~ – entfallen, siehe ADR-NNNN.`
- Eine Regel ist eine prüfbare Aussage. Wo möglich mit konkretem Beispiel
  (Eingabe → Ergebnis).
- Formulierung aus Sicht der Fachlichkeit, nicht der Implementierung
  (keine Funktions- oder Tabellennamen, außer sie sind selbst Teil des Verhaltens).

## Verknüpfung mit Tests und ADRs

- Tests, die eine Regel absichern, nennen die ID im Docstring:
  `"""SALDO-5: leerer Werktag bis heute zählt mit vollem Soll."""`
  Damit findet `grep -rn SALDO-5` Spec, Tests und Code.
- Ist eine Regel beschlossen, aber noch nicht umgesetzt, steht darunter
  `*(offen: <wie es derzeit ist>)*` und im [Backlog](../backlog.md) gibt es
  einen Eintrag dazu. Mit der Umsetzung wird die Markierung entfernt.
- Begründungen stehen nicht in der Spec, sondern im ADR, auf das die Regel
  verweist (`→ ADR-0004`).

## Änderungen

Eine Verhaltensänderung ändert Spec, Code und Tests im selben Commit.

## Bereiche

| Kürzel | Datei | Inhalt |
| ------ | ----- | ------ |
| ERF    | [erfassung.md](erfassung.md) | Einträge, Sammeleintrag, Stempeln, Rundung |
| PAUSE  | [pausen.md](pausen.md) | Pausenabzug nach ArbZG §4 |
| SALDO  | [saldo.md](saldo.md) | Soll, Ist, Saldo, Startdatum, Jahreswechsel |
| FEIER  | [feiertage.md](feiertage.md) | gesetzliche Feiertage |
| NUTZ   | [nutzerinnen.md](nutzerinnen.md) | Zugang, Timeout, Verwaltung, Firmeneinstellungen |
| UI     | [oberflaeche.md](oberflaeche.md) | Anzeigeformate, Startseite, Dashboard-Aufbau |
