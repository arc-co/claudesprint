"""Tests for IssueService."""

from pathlib import Path

from claudesprint.services.issue_service import IssueService


class TestReadLogTail:
    """Tests for read_log_tail method."""

    def test_read_log_tail_empty_when_no_log(self, tmp_path: Path) -> None:
        """Returns empty string when log file doesn't exist."""
        service = IssueService(tmp_path)
        result = service.read_log_tail()
        assert result == ""

    def test_read_log_tail_returns_all_lines_when_fewer_than_limit(
        self, tmp_path: Path
    ) -> None:
        """Returns all lines when fewer than num_lines exist."""
        service = IssueService(tmp_path)
        service.append_log("Line 1")
        service.append_log("Line 2")
        service.append_log("Line 3")

        result = service.read_log_tail(num_lines=10)
        lines = result.split("\n")

        assert len(lines) == 3
        assert "Line 1" in lines[0]
        assert "Line 2" in lines[1]
        assert "Line 3" in lines[2]

    def test_read_log_tail_returns_last_n_lines(self, tmp_path: Path) -> None:
        """Returns only the last N lines when more than N exist."""
        service = IssueService(tmp_path)
        for i in range(10):
            service.append_log(f"Line {i}")

        result = service.read_log_tail(num_lines=3)
        lines = result.split("\n")

        assert len(lines) == 3
        assert "Line 7" in lines[0]
        assert "Line 8" in lines[1]
        assert "Line 9" in lines[2]

    def test_read_log_tail_default_is_20_lines(self, tmp_path: Path) -> None:
        """Default num_lines is 20."""
        service = IssueService(tmp_path)
        for i in range(30):
            service.append_log(f"Line {i}")

        result = service.read_log_tail()
        lines = result.split("\n")

        assert len(lines) == 20
        assert "Line 10" in lines[0]
        assert "Line 29" in lines[19]


class TestAppendLog:
    """Tests for append_log method."""

    def test_append_log_creates_file(self, tmp_path: Path) -> None:
        """Creates log file if it doesn't exist."""
        service = IssueService(tmp_path)
        result = service.append_log("Test entry")

        assert result is True
        assert service.current_issue_log.exists()

    def test_append_log_adds_timestamp(self, tmp_path: Path) -> None:
        """Each entry has a timestamp prefix."""
        service = IssueService(tmp_path)
        service.append_log("Test entry")

        content = service.current_issue_log.read_text()
        # Timestamp format: [YYYY-MM-DDTHH:MM:SSZ]
        assert content.startswith("[20")
        assert "]" in content
        assert "Test entry" in content


class TestReadLog:
    """Tests for read_log method."""

    def test_read_log_empty_when_no_file(self, tmp_path: Path) -> None:
        """Returns empty list when log doesn't exist."""
        service = IssueService(tmp_path)
        result = service.read_log()
        assert result == []

    def test_read_log_returns_all_entries(self, tmp_path: Path) -> None:
        """Returns all log entries as list."""
        service = IssueService(tmp_path)
        service.append_log("Entry 1")
        service.append_log("Entry 2")
        service.append_log("Entry 3")

        result = service.read_log()
        assert len(result) == 3


class TestClearLog:
    """Tests for clear_log method."""

    def test_clear_log_removes_file(self, tmp_path: Path) -> None:
        """Clears log by removing the file."""
        service = IssueService(tmp_path)
        service.append_log("Entry")
        assert service.current_issue_log.exists()

        result = service.clear_log()
        assert result is True
        assert not service.current_issue_log.exists()

    def test_clear_log_succeeds_when_no_file(self, tmp_path: Path) -> None:
        """Succeeds even when log doesn't exist."""
        service = IssueService(tmp_path)
        result = service.clear_log()
        assert result is True
