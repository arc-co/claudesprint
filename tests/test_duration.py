"""Tests for duration parsing and formatting utilities."""

import pytest

from claudesprint.utils.duration import format_duration, parse_duration


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_format_seconds_only(self) -> None:
        assert format_duration(45) == "45s"
        assert format_duration(0) == "0s"
        assert format_duration(59) == "59s"

    def test_format_minutes_and_seconds(self) -> None:
        assert format_duration(60) == "1m 0s"
        assert format_duration(90) == "1m 30s"
        assert format_duration(3599) == "59m 59s"

    def test_format_hours_and_minutes(self) -> None:
        assert format_duration(3600) == "1h 0m"
        assert format_duration(3665) == "1h 1m"
        assert format_duration(7200) == "2h 0m"
        assert format_duration(5400) == "1h 30m"

    def test_format_negative(self) -> None:
        assert format_duration(-1) == "0s"
        assert format_duration(-100) == "0s"


class TestParseDurationSimpleFormat:
    """Tests for parse_duration with simple format (backward compatibility)."""

    def test_parse_seconds(self) -> None:
        assert parse_duration("45s") == 45
        assert parse_duration("0s") == 0
        assert parse_duration("120s") == 120

    def test_parse_minutes(self) -> None:
        assert parse_duration("5m") == 300
        assert parse_duration("1m") == 60
        assert parse_duration("90m") == 5400

    def test_parse_hours(self) -> None:
        assert parse_duration("1h") == 3600
        assert parse_duration("2h") == 7200
        assert parse_duration("24h") == 86400

    def test_parse_combined(self) -> None:
        assert parse_duration("1h30m") == 5400
        assert parse_duration("2h15m30s") == 8130
        assert parse_duration("1h1m1s") == 3661

    def test_parse_bare_numbers(self) -> None:
        assert parse_duration("45") == 45
        assert parse_duration("0") == 0
        assert parse_duration("3600") == 3600

    def test_parse_with_whitespace(self) -> None:
        assert parse_duration("  45s  ") == 45
        assert parse_duration("1h 30m") == 5400
        assert parse_duration(" 1h  30m ") == 5400

    def test_parse_case_insensitive(self) -> None:
        assert parse_duration("1H30M") == 5400
        assert parse_duration("45S") == 45
        assert parse_duration("5M") == 300

    def test_parse_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty duration string"):
            parse_duration("")
        with pytest.raises(ValueError, match="Empty duration string"):
            parse_duration("   ")

    def test_parse_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("abc")
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("1x")
        with pytest.raises(ValueError, match="Invalid duration format"):
            parse_duration("h30m")


class TestParseDurationISO8601:
    """Tests for parse_duration with ISO 8601 format."""

    def test_parse_iso_seconds(self) -> None:
        assert parse_duration("PT45S") == 45
        assert parse_duration("PT0S") == 0
        assert parse_duration("PT120S") == 120

    def test_parse_iso_minutes(self) -> None:
        assert parse_duration("PT5M") == 300
        assert parse_duration("PT1M") == 60
        assert parse_duration("PT90M") == 5400

    def test_parse_iso_hours(self) -> None:
        assert parse_duration("PT1H") == 3600
        assert parse_duration("PT2H") == 7200
        assert parse_duration("PT24H") == 86400

    def test_parse_iso_combined(self) -> None:
        assert parse_duration("PT1H30M") == 5400
        assert parse_duration("PT2H15M30S") == 8130
        assert parse_duration("PT1H1M1S") == 3661

    def test_parse_iso_days(self) -> None:
        assert parse_duration("P1D") == 86400
        assert parse_duration("P7D") == 604800
        assert parse_duration("P1DT12H") == 129600

    def test_parse_iso_weeks(self) -> None:
        assert parse_duration("P1W") == 604800
        assert parse_duration("P2W") == 1209600

    def test_parse_iso_with_whitespace(self) -> None:
        assert parse_duration("  PT45S  ") == 45
        assert parse_duration(" P1D ") == 86400

    def test_parse_iso_fractional_seconds(self) -> None:
        # Fractional seconds should be truncated to int
        assert parse_duration("PT1.5S") == 1
        assert parse_duration("PT0.9S") == 0

    def test_parse_iso_negative(self) -> None:
        assert parse_duration("-PT1H") == -3600
        assert parse_duration("-PT30M") == -1800

    def test_parse_iso_years_raises(self) -> None:
        with pytest.raises(ValueError, match="years or months"):
            parse_duration("P1Y")
        with pytest.raises(ValueError, match="years or months"):
            parse_duration("P2Y3M")

    def test_parse_iso_months_raises(self) -> None:
        with pytest.raises(ValueError, match="years or months"):
            parse_duration("P6M")
        with pytest.raises(ValueError, match="years or months"):
            parse_duration("P1M15D")

    def test_parse_iso_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid ISO 8601 duration format"):
            parse_duration("PXYZ")
        with pytest.raises(ValueError, match="Invalid ISO 8601 duration format"):
            parse_duration("P")

    def test_parse_iso_empty_time(self) -> None:
        # "PT" is a valid ISO 8601 duration representing 0 seconds
        assert parse_duration("PT") == 0


class TestParseDurationEquivalence:
    """Tests verifying simple and ISO 8601 formats produce the same results."""

    def test_equivalence_seconds(self) -> None:
        assert parse_duration("45s") == parse_duration("PT45S")
        assert parse_duration("120s") == parse_duration("PT120S")

    def test_equivalence_minutes(self) -> None:
        assert parse_duration("5m") == parse_duration("PT5M")
        assert parse_duration("90m") == parse_duration("PT90M")

    def test_equivalence_hours(self) -> None:
        assert parse_duration("1h") == parse_duration("PT1H")
        assert parse_duration("24h") == parse_duration("PT24H")

    def test_equivalence_combined(self) -> None:
        assert parse_duration("1h30m") == parse_duration("PT1H30M")
        assert parse_duration("2h15m30s") == parse_duration("PT2H15M30S")

    def test_equivalence_large_values(self) -> None:
        # 1 day = 24 hours
        assert parse_duration("24h") == parse_duration("P1D")
        # 1 week = 168 hours
        assert parse_duration("168h") == parse_duration("P1W")
