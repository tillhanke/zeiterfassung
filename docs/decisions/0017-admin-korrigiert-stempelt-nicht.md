# 0017 – Admin korrigiert Einträge, stempelt aber nicht

- **Status:** Akzeptiert
- **Datum:** 2026-10-22
- **Betrifft:** NUTZ-10, UI-4

## Kontext

Admin hat Zugriff auf alle Dashboards (NUTZ-2). Bisher waren dort auch
„Anfang"/„Ende" aktiv. Am gemeinsamen Gerät konnte Admin damit versehentlich
für eine andere Person einstempeln. Gestempelte Zeiten sollen außerdem
belegen, dass die Nutzerin selbst gestempelt hat.

## Entscheidung

Wir erlauben Admin, Einträge aller Nutzerinnen anzulegen, zu ändern und zu
löschen, aber nicht zu stempeln. Die Oberfläche zeigt in der Admin-Ansicht
keinen Stempel-Button, und der Server lehnt Stempeln als Admin ab.

## Alternativen

- **Admin darf alles** – bequemer, aber Fehlbuchungen am gemeinsamen Gerät
  wären leicht möglich.
- **Admin nur lesend** – Korrekturen müssten dann immer die Nutzerin selbst
  machen, auch bei Fehlern, die Admin bemerkt.

## Konsequenzen

- Vergessene Stempelungen korrigiert Admin über „Ändern" mit konkreten
  Uhrzeiten statt über „Anfang"/„Ende".
