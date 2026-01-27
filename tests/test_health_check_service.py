"""Tests for HealthCheckService."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from claudesprint.services.health_check_service import (
    CheckResult,
    CheckStatus,
    HealthCheckService,
    HealthReport,
)


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_is_ok_when_status_ok(self) -> None:
        """Test is_ok returns True for OK status."""
        result = CheckResult(
            name="Test",
            status=CheckStatus.OK,
            message="All good",
        )
        assert result.is_ok is True
        assert result.is_error is False

    def test_is_error_when_status_error(self) -> None:
        """Test is_error returns True for ERROR status."""
        result = CheckResult(
            name="Test",
            status=CheckStatus.ERROR,
            message="Failed",
        )
        assert result.is_ok is False
        assert result.is_error is True

    def test_warning_status(self) -> None:
        """Test WARNING status is neither OK nor ERROR."""
        result = CheckResult(
            name="Test",
            status=CheckStatus.WARNING,
            message="Warning",
        )
        assert result.is_ok is False
        assert result.is_error is False

    def test_fixable_with_command(self) -> None:
        """Test fixable property with fix_command."""
        result = CheckResult(
            name="Test",
            status=CheckStatus.ERROR,
            message="Missing",
            fixable=True,
            fix_command="pip install something",
        )
        assert result.fixable is True
        assert result.fix_command == "pip install something"


class TestHealthReport:
    """Tests for HealthReport dataclass."""

    def test_is_healthy_with_all_ok(self) -> None:
        """Test is_healthy returns True when all checks pass."""
        report = HealthReport()
        report.add(CheckResult("Test1", CheckStatus.OK, "OK"))
        report.add(CheckResult("Test2", CheckStatus.OK, "OK"))

        assert report.is_healthy is True
        assert report.error_count == 0

    def test_is_healthy_false_with_error(self) -> None:
        """Test is_healthy returns False when any check has error."""
        report = HealthReport()
        report.add(CheckResult("Test1", CheckStatus.OK, "OK"))
        report.add(CheckResult("Test2", CheckStatus.ERROR, "Failed"))

        assert report.is_healthy is False
        assert report.error_count == 1

    def test_has_warnings(self) -> None:
        """Test has_warnings property."""
        report = HealthReport()
        report.add(CheckResult("Test1", CheckStatus.OK, "OK"))
        report.add(CheckResult("Test2", CheckStatus.WARNING, "Warning"))

        assert report.has_warnings is True
        assert report.warning_count == 1
        assert report.is_healthy is True  # Warnings don't fail health check

    def test_fixable_issues(self) -> None:
        """Test fixable_issues returns only fixable non-OK issues."""
        report = HealthReport()
        report.add(CheckResult("Test1", CheckStatus.OK, "OK", fixable=True))
        report.add(
            CheckResult(
                "Test2",
                CheckStatus.ERROR,
                "Failed",
                fixable=True,
                fix_command="fix it",
            )
        )
        report.add(CheckResult("Test3", CheckStatus.ERROR, "Failed", fixable=False))

        fixable = report.fixable_issues
        assert len(fixable) == 1
        assert fixable[0].name == "Test2"


class TestHealthCheckService:
    """Tests for HealthCheckService."""

    def test_check_python_version_passes(self) -> None:
        """Test Python version check passes for current version."""
        service = HealthCheckService()
        result = service.check_python_version()

        # Current Python should pass (we require 3.10+ to run tests)
        assert result.status == CheckStatus.OK
        assert "Python" in result.message

    def test_check_python_version_verbose(self) -> None:
        """Test Python version check includes details when verbose."""
        service = HealthCheckService()
        result = service.check_python_version(verbose=True)

        assert result.details is not None
        assert sys.version in result.details

    @patch("claudesprint.services.health_check_service.sys")
    def test_check_python_version_fails_old_version(
        self, mock_sys: MagicMock
    ) -> None:
        """Test Python version check fails for old version."""
        mock_sys.version_info = (3, 9, 0)
        mock_sys.version = "3.9.0"

        service = HealthCheckService()
        result = service.check_python_version()

        assert result.status == CheckStatus.ERROR
        assert "3.9" in result.message
        assert "3.10" in result.message

    def test_check_required_packages_passes(self) -> None:
        """Test required packages check passes when all installed."""
        service = HealthCheckService()
        result = service.check_required_packages()

        # All required packages should be installed in test environment
        assert result.status == CheckStatus.OK

    def test_check_required_packages_verbose(self) -> None:
        """Test required packages check includes details when verbose."""
        service = HealthCheckService()
        result = service.check_required_packages(verbose=True)

        assert result.details is not None
        # Should list some packages
        for pkg in ["rich", "typer", "pydantic"]:
            assert pkg in result.details

    @patch.object(HealthCheckService, "_is_package_installed")
    def test_check_required_packages_missing(
        self, mock_installed: MagicMock
    ) -> None:
        """Test required packages check fails when packages missing."""
        # Simulate some packages missing
        def is_installed(pkg: str) -> bool:
            return pkg != "httpx"

        mock_installed.side_effect = is_installed

        service = HealthCheckService()
        result = service.check_required_packages()

        assert result.status == CheckStatus.ERROR
        assert "httpx" in result.message
        assert result.fixable is True
        assert "pip install" in (result.fix_command or "")

    @patch("claudesprint.services.health_check_service.shutil.which")
    def test_check_claude_cli_not_found(self, mock_which: MagicMock) -> None:
        """Test Claude CLI check fails when not in PATH."""
        mock_which.return_value = None

        service = HealthCheckService()
        result = service.check_claude_cli()

        assert result.status == CheckStatus.ERROR
        assert "not found" in result.message.lower()

    @patch("claudesprint.services.health_check_service.shutil.which")
    @patch("claudesprint.services.health_check_service.subprocess.run")
    def test_check_claude_cli_found(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        """Test Claude CLI check passes when found."""
        mock_which.return_value = "/usr/local/bin/claude"
        mock_run.return_value = MagicMock(
            stdout="claude version 1.0.0",
            stderr="",
            returncode=0,
        )

        service = HealthCheckService()
        result = service.check_claude_cli()

        assert result.status == CheckStatus.OK
        assert "installed" in result.message.lower()

    @patch("claudesprint.services.health_check_service.subprocess.run")
    @patch("claudesprint.services.health_check_service.shutil.which")
    def test_check_claude_cli_version_fails(
        self, mock_which: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test Claude CLI check warns when version check fails."""
        import subprocess

        mock_which.return_value = "/usr/local/bin/claude"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=10)

        service = HealthCheckService()
        result = service.check_claude_cli()

        assert result.status == CheckStatus.WARNING
        assert "version check failed" in result.message.lower()

    def test_check_project_structure_no_claudesprint_dir(
        self, tmp_path: Path
    ) -> None:
        """Test project structure check warns when no .claudesprint dir."""
        service = HealthCheckService(tmp_path)
        result = service.check_project_structure()

        assert result.status == CheckStatus.WARNING
        assert ".claudesprint" in result.message
        assert result.fixable is True

    def test_check_project_structure_exists(self, tmp_path: Path) -> None:
        """Test project structure check passes when configured."""
        # Create expected structure
        claudesprint_dir = tmp_path / ".claudesprint"
        claudesprint_dir.mkdir()
        (claudesprint_dir / "state").mkdir()
        (claudesprint_dir / "prompts").mkdir()

        service = HealthCheckService(tmp_path)
        result = service.check_project_structure()

        assert result.status == CheckStatus.OK

    def test_check_project_structure_missing_subdirs(
        self, tmp_path: Path
    ) -> None:
        """Test project structure check warns when subdirs missing."""
        # Create partial structure
        claudesprint_dir = tmp_path / ".claudesprint"
        claudesprint_dir.mkdir()

        service = HealthCheckService(tmp_path)
        result = service.check_project_structure()

        assert result.status == CheckStatus.WARNING
        assert "Missing directories" in result.message

    @patch("claudesprint.services.health_check_service.shutil.which")
    def test_check_optional_deps_npm_not_found(
        self, mock_which: MagicMock
    ) -> None:
        """Test optional deps check warns when npm not found."""
        mock_which.return_value = None

        service = HealthCheckService()
        results = service.check_optional_deps()

        # Should have results for both agent-browser and npm
        assert len(results) >= 2

        # All should be warnings since nothing is found
        for result in results:
            assert result.status == CheckStatus.WARNING
            assert "(optional)" in result.name

    @patch("claudesprint.services.health_check_service.shutil.which")
    def test_check_optional_deps_found(self, mock_which: MagicMock) -> None:
        """Test optional deps check passes when deps found."""
        mock_which.return_value = "/usr/local/bin/something"

        service = HealthCheckService()
        results = service.check_optional_deps()

        for result in results:
            assert result.status == CheckStatus.OK

    def test_run_all_checks(self) -> None:
        """Test run_all_checks returns a complete report."""
        service = HealthCheckService()
        report = service.run_all_checks()

        # Should have multiple checks
        assert len(report.checks) >= 4

        # Should have named checks
        check_names = [c.name for c in report.checks]
        assert "Python Version" in check_names
        assert "Required Packages" in check_names
        assert "Claude CLI" in check_names
        assert "Project Structure" in check_names

    def test_run_all_checks_verbose(self) -> None:
        """Test run_all_checks includes details when verbose."""
        service = HealthCheckService()
        report = service.run_all_checks(verbose=True)

        # At least some checks should have details
        checks_with_details = [c for c in report.checks if c.details]
        assert len(checks_with_details) > 0


class TestHealthCheckServiceFix:
    """Tests for auto-fix functionality."""

    @patch("claudesprint.services.health_check_service.subprocess.run")
    def test_attempt_fix_pip_install(self, mock_run: MagicMock) -> None:
        """Test attempting to fix with pip install."""
        mock_run.return_value = MagicMock(
            stdout="Successfully installed",
            stderr="",
            returncode=0,
        )

        check = CheckResult(
            name="Test",
            status=CheckStatus.ERROR,
            message="Missing",
            fixable=True,
            fix_command="pip install httpx",
        )

        service = HealthCheckService()
        result = service.attempt_fix(check)

        assert result is True
        mock_run.assert_called_once()

    @patch("claudesprint.services.health_check_service.subprocess.run")
    def test_attempt_fix_pip_install_fails(self, mock_run: MagicMock) -> None:
        """Test pip install fix failure."""
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="Error",
            returncode=1,
        )

        check = CheckResult(
            name="Test",
            status=CheckStatus.ERROR,
            message="Missing",
            fixable=True,
            fix_command="pip install nonexistent",
        )

        service = HealthCheckService()
        result = service.attempt_fix(check)

        assert result is False

    def test_attempt_fix_not_fixable(self) -> None:
        """Test attempt_fix returns False for non-fixable issues."""
        check = CheckResult(
            name="Test",
            status=CheckStatus.ERROR,
            message="Error",
            fixable=False,
        )

        service = HealthCheckService()
        result = service.attempt_fix(check)

        assert result is False

    def test_attempt_fix_claudesprint_command(self) -> None:
        """Test claudesprint commands are not auto-run."""
        check = CheckResult(
            name="Test",
            status=CheckStatus.WARNING,
            message="Missing",
            fixable=True,
            fix_command="claudesprint initrepo",
        )

        service = HealthCheckService()
        result = service.attempt_fix(check)

        # Should return False - manual run required
        assert result is False

    @patch("claudesprint.services.health_check_service.subprocess.run")
    def test_fix_all(self, mock_run: MagicMock) -> None:
        """Test fix_all attempts to fix all fixable issues."""
        mock_run.return_value = MagicMock(
            stdout="OK",
            stderr="",
            returncode=0,
        )

        report = HealthReport()
        report.add(CheckResult("OK", CheckStatus.OK, "OK"))
        report.add(
            CheckResult(
                "Fix1",
                CheckStatus.ERROR,
                "Error",
                fixable=True,
                fix_command="pip install a",
            )
        )
        report.add(
            CheckResult(
                "Fix2",
                CheckStatus.WARNING,
                "Warning",
                fixable=True,
                fix_command="pip install b",
            )
        )
        report.add(
            CheckResult(
                "NoFix",
                CheckStatus.ERROR,
                "Error",
                fixable=False,
            )
        )

        service = HealthCheckService()
        successful, failed = service.fix_all(report)

        assert successful == 2
        assert failed == 0
        assert mock_run.call_count == 2


class TestCheckStatus:
    """Tests for CheckStatus enum."""

    def test_status_values(self) -> None:
        """Test check status string values."""
        assert CheckStatus.OK.value == "ok"
        assert CheckStatus.WARNING.value == "warning"
        assert CheckStatus.ERROR.value == "error"


class TestHealthReportEdgeCases:
    """Edge case tests for HealthReport."""

    def test_empty_report_is_healthy(self) -> None:
        """Test empty report is considered healthy."""
        report = HealthReport()
        assert report.is_healthy is True
        assert report.has_warnings is False
        assert report.error_count == 0
        assert report.warning_count == 0
        assert report.fixable_issues == []


class TestPackageVersionMethods:
    """Tests for package version checking methods."""

    def test_get_package_version_returns_none_for_nonexistent(self) -> None:
        """Test _get_package_version returns None for nonexistent package."""
        service = HealthCheckService()
        result = service._get_package_version("nonexistent-package-xyz-123")
        assert result is None

    def test_get_package_version_returns_version_for_installed(self) -> None:
        """Test _get_package_version returns version for installed package."""
        service = HealthCheckService()
        # rich should be installed in test environment
        result = service._get_package_version("rich")
        assert result is not None
        assert isinstance(result, str)


class TestAttemptFixCallbacks:
    """Tests for attempt_fix callback functionality."""

    @patch("claudesprint.services.health_check_service.subprocess.run")
    def test_attempt_fix_calls_on_output_callback(
        self, mock_run: MagicMock
    ) -> None:
        """Test attempt_fix calls on_output callback with command output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Installing package...\nDone",
            stderr="Warning: something",
        )

        check = CheckResult(
            name="Test",
            status=CheckStatus.ERROR,
            message="Missing",
            fixable=True,
            fix_command="pip install something",
        )

        output_lines: list[str] = []
        service = HealthCheckService()
        result = service.attempt_fix(check, on_output=output_lines.append)

        assert result is True
        assert len(output_lines) == 2
        assert "Installing" in output_lines[0]
        assert "Warning" in output_lines[1]

    @patch("claudesprint.services.health_check_service.subprocess.run")
    def test_attempt_fix_npm_install(self, mock_run: MagicMock) -> None:
        """Test attempting to fix with npm install."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="added 1 package",
            stderr="",
        )

        check = CheckResult(
            name="Test",
            status=CheckStatus.WARNING,
            message="Not installed",
            fixable=True,
            fix_command="npm install -g agent-browser",
        )

        service = HealthCheckService()
        result = service.attempt_fix(check)

        assert result is True
        mock_run.assert_called_once()
        # Verify shlex.split was used (command should be a list)
        call_args = mock_run.call_args
        assert call_args[0][0] == ["npm", "install", "-g", "agent-browser"]


class TestFixAllMixedResults:
    """Tests for fix_all with mixed success/failure results."""

    @patch("claudesprint.services.health_check_service.subprocess.run")
    def test_fix_all_counts_failures_correctly(
        self, mock_run: MagicMock
    ) -> None:
        """Test fix_all correctly counts successes and failures."""
        # First call succeeds, second fails
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="OK", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="Error"),
        ]

        report = HealthReport()
        report.add(
            CheckResult(
                "Fix1",
                CheckStatus.ERROR,
                "Error",
                fixable=True,
                fix_command="pip install a",
            )
        )
        report.add(
            CheckResult(
                "Fix2",
                CheckStatus.ERROR,
                "Error",
                fixable=True,
                fix_command="pip install b",
            )
        )

        service = HealthCheckService()
        successful, failed = service.fix_all(report)

        assert successful == 1
        assert failed == 1
        assert mock_run.call_count == 2
