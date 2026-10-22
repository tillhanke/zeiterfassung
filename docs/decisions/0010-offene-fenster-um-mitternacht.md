# 0010 – Offene Zeitfenster werden um Mitternacht verworfen

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** ERF-14

## Kontext

Vergisst eine Nutzerin „Ende", bleibt das Fenster offen und blockiert
Stempeln an allen folgenden Tagen, bis sie es manuell korrigiert. Schichten
über Mitternacht gibt es im Betrieb nicht.

## Entscheidung

Ein am Ende seines Tages (23:59) noch offenes Zeitfenster wird gelöscht;
abgeschlossene Fenster des Tages bleiben. Der Tag wird als „Stempeln
unvollständig – bitte nachtragen" markiert, bis die Nutzerin ihn bearbeitet.
Fehlende Stunden zählen bis dahin ins Minus.

## Alternativen

- **Offen lassen (bisher)** – blockiert das Stempeln am Folgetag.
- **Automatisch mit Endzeit schließen** – erfindet Arbeitszeit, die so nicht
  stattgefunden hat.
- **Markieren ohne Minus** – das Minus erinnert wirksamer ans Nachtragen.

## Konsequenzen

- Die Markierung braucht eine Schemaänderung (→ ADR-0012).
- Ohne Hintergrundjob wird das Verwerfen beim nächsten Zugriff ausgeführt;
  das Ergebnis muss dasselbe sein wie um 23:59.
