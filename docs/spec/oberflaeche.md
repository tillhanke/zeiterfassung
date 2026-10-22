# Oberfläche (`UI`)

Wie Zahlen, Daten und die wichtigsten Bildschirme dargestellt werden. Die
Oberfläche ist für ein gemeinsames Gerät im Betrieb ausgelegt (PC oder
Tablet, kioskartig).

## Begriffe

- **Dauer** – Arbeitszeit, Soll, Ist oder Saldo in Stunden.
- **Karte „Heute"** – Bereich oben im Dashboard mit dem Stempelstatus des
  heutigen Tages.

## Regeln

### Formate

- **UI-1** – Dauern werden als Stunden und Minuten (`h:mm`) angezeigt, auf
  volle Minuten gerundet; Uhrzeiten im 24-Stunden-Format (`HH:MM`). Salden
  und Abweichungen tragen immer ein Vorzeichen (`+`, `−`, `±` bei null).
  Beispiel: 7,75 h → `7:45`, −1,5 h → `−1:30`, 0 h Saldo → `±0:00`.
  Das gilt auch für die Live-Vorschau im Eintragsformular. → ADR-0016
- **UI-2** – Datumsangaben sind deutsch formatiert: `22.10.2026`, in
  Tageslisten kurz `Do 22.10.`, in Überschriften lang
  `Donnerstag, 22. Oktober 2026`.

### Bildschirme

- **UI-3** – Die Startseite zeigt die aktiven Nutzerinnen als große
  Kacheln; eine Kachel zeigt an, wenn die Nutzerin heute gerade
  eingestempelt ist. Der Zugang zur Verwaltung ist ein unauffälliger Link
  darunter. Die Topbar zeigt die aktive Identität und „Abmelden" (zurück zur
  Startseite), aber keine Auswahlliste. → ADR-0018
- **UI-4** – Das Dashboard einer Nutzerin beginnt mit der Karte „Heute"
  (Status, laufende Zeit, „Anfang"/„Ende") und dem aktuellen Gesamtsaldo.
  Die Karte zeigt immer den heutigen Tag, auch wenn ein anderer Monat
  angezeigt wird. Ist Stempeln nicht möglich (z. B. Feiertag, Urlaub/Krank,
  vor dem Startdatum, Admin-Ansicht), steht dort der Grund statt des Buttons.
  In der Tagesliste wird nicht gestempelt.
- **UI-5** – Sieht Admin das Dashboard einer Nutzerin, steht darüber eine
  Hinweisleiste mit ihrem Namen und einem Link zurück zur Übersicht.

## Nicht im Umfang

- Dunkles Farbschema.

## Verweise

- ADRs: 0016, 0017, 0018
- Tests: `tests/test_ui.py`
