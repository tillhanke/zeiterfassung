# 0014 – Deployment per Docker oder systemd

- **Status:** Akzeptiert
- **Datum:** 2026-05-11
- **Betrifft:** `Dockerfile`, `compose.yaml`, `deploy/`

## Kontext

Die App läuft auf kleinen Servern im Betrieb, teils mit Docker, teils ohne.

## Entscheidung

Wir unterstützen zwei gleichwertige Wege: Container (Dockerfile, compose,
`instance/` als Volume) und einen gehärteten systemd-Dienst. Beide setzen
`SECRET_KEY` aus der Umgebung und laufen in der Zeitzone Europe/Berlin,
damit Stempelzeiten der Ortszeit entsprechen.

## Alternativen

- **Nur Docker** – setzt Docker auf jedem Zielsystem voraus.
- **Nur systemd** – schwieriger lokal und auf Nicht-Linux-Systemen.

## Konsequenzen

- Änderungen an Start, Konfiguration oder Datenbank-Init müssen in beiden
  Wegen nachgezogen werden.
