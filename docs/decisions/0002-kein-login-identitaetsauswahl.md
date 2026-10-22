# 0002 – Kein Login: Identitätsauswahl mit Inaktivitäts-Timeout

- **Status:** Akzeptiert
- **Datum:** 2026-05-05 (Timeout ergänzt 2026-10-20)
- **Betrifft:** NUTZ-1, NUTZ-2, NUTZ-3

## Kontext

Die App läuft auf einem gemeinsamen Gerät im Betrieb, an dem alle
Nutzerinnen stempeln, in einer Vertrauensumgebung (kleines Team, internes
Netz). Ein Login mit Passwort würde jeden Stempelvorgang verlangsamen.
Ohne Abmeldung besteht aber das Risiko, dass die nächste Person unter dem
Namen der vorherigen stempelt.

## Entscheidung

Wir verzichten auf Authentifizierung. Die Identität (Nutzerin oder Admin)
wird über eine Auswahl gesetzt. Nach 10 min ohne Eingabe wird sie verworfen
und die Startseite angezeigt, im Browser und zusätzlich serverseitig.

## Alternativen

- **Login mit Passwort/PIN** – sicherer, aber umständlich am gemeinsamen
  Gerät. Bleibt als Idee im Backlog.
- **Kein Timeout** – einfacher, aber Fehlbuchungen unter falschem Namen am
  gemeinsamen Gerät wären wahrscheinlich.

## Konsequenzen

- Jede Person im Netz kann jede Identität wählen, auch Admin. Die App darf
  nur intern erreichbar sein.
- Die Rechteprüfung (NUTZ-2) verhindert Versehen, nicht Missbrauch.
