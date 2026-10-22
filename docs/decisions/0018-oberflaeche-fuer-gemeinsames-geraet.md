# 0018 – Oberfläche für ein gemeinsames Gerät (Kiosk)

- **Status:** Vorgeschlagen
- **Datum:** 2026-10-22
- **Betrifft:** NUTZ-1, UI-3, UI-4

## Kontext

Die App wird überwiegend an einem gemeinsamen PC oder Tablet im Betrieb
benutzt. Die häufigste Handlung ist Ein- und Ausstempeln. Bisher wurde die
Identität über eine Auswahlliste in der Topbar gewechselt, in der „Admin"
gleichrangig neben den Namen stand, und „Anfang"/„Ende" steckte als kleiner
Button in der Tagestabelle.

## Entscheidung

Wir gestalten die Oberfläche für Touch und schnelle Abläufe:

- Startseite mit großen Namenskacheln, Verwaltung als unauffälliger Link.
- Topbar zeigt nur die aktive Identität und „Abmelden"; gewechselt wird
  über die Startseite. „Zeiterfassung" oben links führt immer zur
  Namensauswahl, auch mit aktiver Identität (kein Weiterleiten zum
  eigenen Dashboard).
- Das Dashboard beginnt mit einer Karte „Heute" mit großem Stempel-Button
  und dem Gesamtsaldo; die Monatsliste folgt darunter.

## Alternativen

- **Auswahlliste in der Topbar beibehalten** – schneller Wechsel für Admin,
  aber am gemeinsamen Gerät fehleranfällig und auf Tablets unhandlich.
- **Stempeln direkt auf der Startseite** (Name tippen = stempeln) – noch
  schneller, aber ohne Rückmeldung zum eigenen Saldo und mit höherem Risiko
  von Fehlbuchungen.

## Konsequenzen

- Admin wechselt über „Abmelden" → „Verwaltung" statt über die Topbar.
- Wer die App mit noch aktiver Identität öffnet, sieht die Namensauswahl
  und muss den eigenen Namen erneut antippen.
- Spätere Bildschirme (Eintragsformular, Admin) folgen denselben Mustern:
  große Schaltflächen, eine Hauptaktion pro Bildschirm.
