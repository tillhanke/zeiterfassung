"""Tests für das User-Dashboard.

Hier wird vor allem die Endpunkt-Integration geprüft (Status-Code, Rendering,
Monatsnavigation). Die feingranulare Saldo-Logik ist in test_logic.py
abgedeckt.
"""
from __future__ import annotations

from datetime import date, time

from models import Absence, WorkDay


class TestDashboardRendering:
    def test_get_with_month_params(self, client, login_alice):
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        assert r.status_code == 200
        assert b"Alice" in r.data
        assert b"Mai 2026" in r.data

    def test_default_month_uses_today(self, client, login_alice):
        # Ohne Parameter wird der aktuelle Monat angezeigt; nur prüfen, dass es 200 ist.
        r = client.get(f"/user/{login_alice}")
        assert r.status_code == 200

    def test_invalid_year_falls_back_to_today(self, client, login_alice):
        r = client.get(f"/user/{login_alice}?year=foo&month=bar")
        assert r.status_code == 200

    def test_invalid_month_falls_back(self, client, login_alice):
        r = client.get(f"/user/{login_alice}?year=2026&month=99")
        assert r.status_code == 200

    def test_month_navigation_links_present(self, client, login_alice):
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        # Vor- und Nachbar-Monatslink müssen vorhanden sein.
        assert b"April 2026" in r.data
        assert b"Juni 2026" in r.data

    def test_year_wrap_navigation(self, client, login_alice):
        r = client.get(f"/user/{login_alice}?year=2026&month=1")
        assert b"Dezember 2025" in r.data
        r = client.get(f"/user/{login_alice}?year=2026&month=12")
        assert b"Januar 2027" in r.data


class TestDashboardContent:
    def test_workday_appears_in_table(self, client, login_alice, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(9, 0), time(17, 30))
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        assert b"2026-05-11" in r.data
        assert b"Arbeit" in r.data

    def test_workday_start_and_end_time_shown(self, client, login_alice, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(8, 15), time(16, 45))
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        assert b"08:15" in r.data
        assert b"16:45" in r.data

    def test_multiple_windows_shown(self, client, login_alice, make_workday):
        make_workday(login_alice, date(2026, 5, 11), time(8, 0), time(12, 0))
        make_workday(login_alice, date(2026, 5, 11), time(13, 0), time(17, 15))
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        for t in (b"08:00", b"12:00", b"13:00", b"17:15"):
            assert t in r.data

    def test_table_no_longer_shows_brutto_netto_soll_columns(self, client, login_alice):
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        # Spaltenüberschriften "Brutto"/"Netto"/"Soll" in der Tagestabelle sind weg.
        assert b"<th class=\"text-end\">Brutto</th>" not in r.data
        assert b"<th class=\"text-end\">Netto</th>" not in r.data
        # Soll-Karte oben enthält "Soll" weiterhin, aber kein <th>Soll</th> mehr.
        assert b"<th class=\"text-end\">Soll</th>" not in r.data
        # Stattdessen sind Start und Ende vorhanden.
        assert b"<th class=\"text-end\">Start</th>" in r.data
        assert b"<th class=\"text-end\">Ende</th>" in r.data

    def test_vacation_badge_present(self, client, login_alice, make_absence):
        make_absence(login_alice, date(2026, 5, 11), kind="vacation")
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        assert b"Urlaub" in r.data

    def test_sick_badge_present(self, client, login_alice, make_absence):
        make_absence(login_alice, date(2026, 5, 11), kind="sick")
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        assert b"Krank" in r.data

    def test_holiday_row_rendered(self, client, login_alice):
        # 1.5.2026 = Tag der Arbeit (Fr)
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        assert b"Feiertag" in r.data
        assert b"Tag der Arbeit" in r.data

    def test_future_class_in_current_month(self, client, login_alice, monkeypatch):
        """Wenn heute mitten im Monat ist, müssen future-Tage als solche
        gerendert werden."""
        import logic

        class _Frozen(date):
            @classmethod
            def today(cls):
                return date(2026, 5, 11)

        monkeypatch.setattr(logic, "date", _Frozen)
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        assert b"day-row future" in r.data
        assert b"noch offen" in r.data

    def test_no_future_class_in_past_month(self, client, login_alice, monkeypatch):
        import logic

        class _Frozen(date):
            @classmethod
            def today(cls):
                return date(2026, 5, 11)

        monkeypatch.setattr(logic, "date", _Frozen)
        r = client.get(f"/user/{login_alice}?year=2026&month=3")
        assert b"day-row future" not in r.data

    def test_admin_can_view_user_dashboard(self, client, login_admin, alice_id):
        r = client.get(f"/user/{alice_id}?year=2026&month=5")
        assert r.status_code == 200

    def test_bulk_button_present(self, client, login_alice):
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        assert b"Mehrere Tage" in r.data

    def test_add_button_links_to_today(self, client, login_alice):
        r = client.get(f"/user/{login_alice}?year=2026&month=5")
        assert b"Tag eintragen" in r.data
