"""Tests für Anzeigeformate und Aufbau der Oberfläche (Spec-Bereich UI)."""
from __future__ import annotations

from datetime import date, datetime, time

import pytest

import logic
from tests.test_clock import freeze_now  # noqa: F401  (Fixture)


class TestFormats:
    @pytest.mark.parametrize(
        "hours, expected",
        [(7.75, "7:45"), (8.0, "8:00"), (0.0, "0:00"), (0.25, "0:15"),
         (-1.5, "−1:30"), (123.5, "123:30"), (1 / 60, "0:01")],
    )
    def test_format_hm(self, hours, expected):
        """UI-1: Dauern als h:mm, auf volle Minuten gerundet."""
        assert logic.format_hm(hours) == expected

    @pytest.mark.parametrize(
        "hours, expected",
        [(0.25, "+0:15"), (-1.5, "−1:30"), (0.0, "±0:00"), (-0.001, "±0:00")],
    )
    def test_format_hm_signed(self, hours, expected):
        """UI-1: Salden immer mit Vorzeichen."""
        assert logic.format_hm(hours, signed=True) == expected

    def test_format_dates(self):
        """UI-2: Datumsangaben deutsch."""
        d = date(2026, 10, 22)
        assert logic.format_date(d) == "22.10.2026"
        assert logic.format_day(d) == "Do 22.10."
        assert logic.format_long_date(d) == "Donnerstag, 22. Oktober 2026"

    def test_format_number(self):
        assert logic.format_number(40.0) == "40"
        assert logic.format_number(38.5) == "38,5"


class TestStartPage:
    def test_users_as_tiles_admin_as_link(self, client, alice_id, bob_id):
        """UI-3: Namen als Kacheln, Verwaltung unauffällig."""
        html = client.get("/").data.decode()
        assert html.count('<button class="zf-tile') == 2
        assert ">Verwaltung</button>" in html
        assert "Als Admin anmelden" not in html

    def test_tile_shows_running_clock(self, client, alice_id, bob_id, make_workday):
        """UI-3: Kachel zeigt, wer gerade eingestempelt ist."""
        make_workday(alice_id, date.today(), time(8, 15), None)
        html = client.get("/").data.decode()
        assert html.count("is-running") == 1
        assert "eingestempelt seit 08:15" in html

    def test_no_identity_dropdown_in_topbar(self, client, login_alice):
        """UI-3: Topbar zeigt die Identität und „Abmelden“, keine Auswahl."""
        html = client.get(f"/user/{login_alice}").data.decode()
        assert 'id="identitySelect"' not in html
        assert ">Abmelden</button>" in html
        assert "Alice" in html


class TestTodayCard:
    def test_today_card_when_other_month_shown(self, client, login_alice, freeze_now):
        """UI-4: Karte „Heute“ mit Stempeln auch beim Blättern."""
        freeze_now(datetime(2026, 5, 11, 8, 0))
        html = client.get(f"/user/{login_alice}?year=2026&month=3").data.decode()
        assert "Montag, 11. Mai 2026" in html
        assert html.count(">Anfang</button>") == 1

    def test_holiday_shows_reason_instead_of_button(self, client, login_alice, freeze_now):
        freeze_now(datetime(2026, 5, 1, 8, 0))
        html = client.get(f"/user/{login_alice}").data.decode()
        assert ">Anfang</button>" not in html
        assert "Heute ist Feiertag (Tag der Arbeit)." in html

    def test_vacation_shows_reason(self, client, login_alice, freeze_now, make_absence):
        make_absence(login_alice, date(2026, 5, 11))
        freeze_now(datetime(2026, 5, 11, 8, 0))
        html = client.get(f"/user/{login_alice}").data.decode()
        assert ">Anfang</button>" not in html
        assert "Für heute ist Urlaub eingetragen." in html

    def test_balance_in_hm(self, client, login_alice, make_workday, freeze_now):
        """UI-1: Gesamtsaldo als h:mm."""
        freeze_now(datetime(2026, 5, 11, 18, 0))
        r = client.get(f"/user/{login_alice}")
        assert b"Aktueller Gesamtsaldo" in r.data
        assert b" h/Woche" in r.data
        assert "40 h/Woche · Soll/Tag 8:00 h".encode() in r.data


class TestAdminView:
    def test_admin_bar_and_no_clock_button(self, client, login_admin, alice_id, freeze_now):
        """UI-5, NUTZ-10: Admin sieht Hinweisleiste und keinen Stempel-Button."""
        freeze_now(datetime(2026, 5, 11, 8, 0))
        html = client.get(f"/user/{alice_id}").data.decode()
        assert "Admin-Ansicht" in html
        assert "Zur Übersicht" in html
        assert ">Anfang</button>" not in html
        assert "Stempeln kann nur die Nutzerin selbst." in html

    def test_user_sees_no_admin_bar(self, client, login_alice):
        html = client.get(f"/user/{login_alice}").data.decode()
        assert "Admin-Ansicht" not in html
