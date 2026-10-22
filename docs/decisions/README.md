# Entscheidungen (ADRs)

Architecture Decision Records halten fest, **warum** etwas so ist, wie es
ist: fachliche und technische Entscheidungen, bei denen es echte
Alternativen gab. Das aktuelle Verhalten selbst steht in der
[Spec](../spec/README.md).

## Wann ein ADR?

Ein ADR lohnt sich, wenn eine spätere Leserin (oder ein Agent) fragen würde
„Warum nicht einfach …?". Typisch:

- Wahl von Technik, Struktur oder Deployment (z. B. SQLite, kein Login)
- fachliche Grundsatzregeln mit Alternativen (z. B. Umgang mit Wochenendarbeit)
- bewusste Auslassungen („machen wir nicht, weil …")

Kein ADR nötig für Bugfixes, reine Umsetzungsdetails oder Dinge ohne
ernsthafte Alternative.

## Format

- Datei: `docs/decisions/NNNN-kurzer-titel.md`, fortlaufend vierstellig nummeriert.
- Vorlage: [`_vorlage.md`](_vorlage.md).
- Kurz halten: eine Bildschirmseite ist die Obergrenze.

## Status und Lebenszyklus

| Status | Bedeutung |
| ------ | --------- |
| Vorgeschlagen | Entwurf, noch nicht bestätigt (z. B. von einem Agenten verfasst) |
| Akzeptiert | Gilt. Inhalt wird nicht mehr geändert |
| Abgelöst durch ADR-NNNN | Durch neue Entscheidung ersetzt |
| Verworfen | Vorgeschlagen, aber nicht angenommen; bleibt als Begründung stehen |

Akzeptierte ADRs sind **unveränderlich**: Ändert sich die Entscheidung, wird
ein neues ADR geschrieben und beim alten nur der Status angepasst.
Tippfehler und Links dürfen korrigiert werden.

Nachträglich dokumentierte Entscheidungen tragen das Datum, an dem sie
ursprünglich getroffen wurden (soweit bekannt, z. B. aus der Git-Historie).

## Übersicht

| Nr. | Titel | Status |
| --- | ----- | ------ |
| [0001](0001-adrs-und-spec-verwenden.md) | Spezifikation und Entscheidungen als Markdown im Repository | Akzeptiert |
| [0002](0002-kein-login-identitaetsauswahl.md) | Kein Login: Identitätsauswahl mit Inaktivitäts-Timeout | Akzeptiert |
| [0003](0003-pausenabzug-nach-tagessumme.md) | Pausenabzug nach Tagessumme mit Anrechnung von Lücken | Akzeptiert |
| [0004](0004-tagessoll-gleichmaessig.md) | Tagessoll gleichmäßig: Wochenstunden / 5 | Akzeptiert |
| [0005](0005-arbeit-ohne-soll-ist-ueberstunde.md) | Arbeit an Wochenende und Feiertag zählt als Überstunden | Akzeptiert |
| [0006](0006-saldo-bis-jetzt.md) | Saldo zählt bis jetzt: keine Zukunft, offene Fenster live | Akzeptiert |
| [0007](0007-startdatum-mit-uebertrag.md) | Startdatum mit Übertrag, frühere Einträge bleiben erhalten | Akzeptiert |
| [0008](0008-nullstellung-jahreswechsel.md) | Nullstellung zum Jahreswechsel als Firmeneinstellung | Akzeptiert |
| [0009](0009-rundung-firmeneinstellung.md) | Rundung beim Stempeln als Firmeneinstellung | Akzeptiert |
| [0010](0010-offene-fenster-um-mitternacht.md) | Offene Zeitfenster werden um Mitternacht verworfen | Akzeptiert |
| [0011](0011-bundesland-einstellbar.md) | Bundesland für Feiertage als Firmeneinstellung | Akzeptiert |
| [0012](0012-sqlite-mit-alembic.md) | SQLite mit Alembic-Migrationen | Akzeptiert |
| [0013](0013-deaktivieren-statt-loeschen.md) | Nutzerinnen deaktivieren statt löschen | Akzeptiert |
| [0014](0014-deployment-docker-und-systemd.md) | Deployment per Docker oder systemd | Akzeptiert |
| [0015](0015-wochenstunden-ohne-grenzen.md) | Wochenstunden ab 0, ohne Obergrenze | Akzeptiert |
| [0016](0016-dauern-als-stunden-minuten.md) | Dauern werden als Stunden:Minuten angezeigt | Akzeptiert |
| [0017](0017-admin-korrigiert-stempelt-nicht.md) | Admin korrigiert Einträge, stempelt aber nicht | Akzeptiert |
| [0018](0018-oberflaeche-fuer-gemeinsames-geraet.md) | Oberfläche für ein gemeinsames Gerät (Kiosk) | Akzeptiert |
