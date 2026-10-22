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
| [0001](0001-adrs-und-spec-verwenden.md) | ADRs und Spec im Repository verwenden | Akzeptiert |
