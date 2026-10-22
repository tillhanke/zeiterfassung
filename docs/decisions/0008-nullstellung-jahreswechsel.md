# 0008 – Nullstellung zum Jahreswechsel als Firmeneinstellung

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** SALDO-11, SALDO-12

## Kontext

Bis 2026-10-22 begann jeder Jahressaldo bei 0. Manche Betriebe übertragen
Über-/Minusstunden ins neue Jahr.

## Entscheidung

Eine firmenweite Einstellung legt fest, ob der Saldo zum Jahreswechsel auf 0
gesetzt wird. Standard ist „an", damit sich das bisherige Verhalten nicht
ändert; ein Übertrag muss bewusst eingeschaltet werden.

Ohne Nullstellung zählt der Saldo ab dem Jahr des Startdatums, ohne
Startdatum ab dem 1.1. des Jahres mit dem ersten Eintrag. Dass dann Werktage
vor dem ersten Eintrag dieses Jahres als Minus zählen, nehmen wir bewusst in
Kauf: Nutzerinnen haben entweder ein Startdatum oder sind ganzjährig dabei.

## Alternativen

- **Einstellung je Nutzerin** – im Betrieb nicht nötig.
- **Zählbeginn ab Tag des ersten Eintrags** – verworfen, siehe oben.

## Konsequenzen

- Wer ohne Startdatum mitten im Jahr beginnt, braucht ein Startdatum, sonst
  ist der Saldo bei ausgeschalteter Nullstellung falsch.
