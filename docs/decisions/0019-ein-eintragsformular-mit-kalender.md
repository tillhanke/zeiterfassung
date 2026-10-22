# 0019 – Ein Eintragsformular mit Kalender statt Einzel- und Sammeleintrag

- **Status:** Vorgeschlagen
- **Datum:** 2026-10-22
- **Betrifft:** ERF-7, ERF-8, ERF-9, ERF-16

## Kontext

Es gab zwei Formulare: „Tag eintragen" (ein Datumsfeld) und „Mehrere Tage"
(Einzeldatum hinzufügen, Zeitraum von–bis, Chips). Nutzerinnen mussten sich
vor dem Eintragen für eins entscheiden, obwohl beide dasselbe speichern.
Der Sammeleintrag war für einfache Fälle („heute krank") zu schwerfällig,
der Einzeleintrag für eine Urlaubswoche zu umständlich. Am Tablet sind
Datumsfelder außerdem mühsam.

## Entscheidung

Wir ersetzen beide durch ein Formular mit Monatskalender. Tage werden
angetippt (einzeln) oder im Modus „Zeitraum" über ersten und letzten Tag
gewählt; ein Zeitraum lässt Wochenenden und Feiertage aus. Vorhandene
Einträge sind im Kalender markiert. Die Vorlage „Wie letzter Arbeitstag"
übernimmt dessen Zeitfenster. Serverseitig behandelt eine Funktion einen
wie mehrere Tage; der alte Sammeleintrag-Pfad leitet auf das Formular um.

## Alternativen

- **Zwei Formulare beibehalten, nur gestalterisch verbessern** – weniger
  Umbau, aber die Entscheidung „einer oder mehrere?" bliebe.
- **Bearbeiten direkt in der Tagesliste (inline)** – schnell für einen Tag,
  aber für Zeiträume ungeeignet; kann später ergänzend kommen.

## Konsequenzen

- ERF-7/ERF-8 unterscheiden nach Anzahl gewählter Tage statt nach Formular.
- Der Kalender braucht JavaScript; ohne JS ist kein Eintragen möglich
  (Zielgerät ist ein bekannter Browser im Betrieb).
