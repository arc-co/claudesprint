"""Tests for CLI hook command with session awareness."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from claudesprint.cli import app

runner = CliRunner()


class TestHookSessionAwareness:
    """Tests for hook command session-aware behavior."""

    def test_hook_exits_0_when_no_session(self) -> None:
        """Test that hook allows blocked commands when no session is active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No sprint.lock exists - no active session
            project_root = Path(tmpdir)
            (project_root / ".claude").mkdir()

            # Mock discover_project_root to return our temp directory
            with patch(
                "claudesprint.services.path_service.PathService.discover_project_root",
                return_value=project_root,
            ):
                # Input that would normally be blocked (watch command)
                json_input = '{"tool_input":{"command":"npm test --watch"}}'
                result = runner.invoke(
                    app,
                    ["hook", "--type", "server-guard"],
                    input=json_input,
                )

                # Should exit 0 (allow) because no session is active
                assert result.exit_code == 0

    def test_hook_executes_guard_when_session_active(self) -> None:
        """Test that hook executes guard logic when session is active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            # Create sprint.lock to indicate active session
            state_dir = project_root / ".claudesprint" / "state"
            state_dir.mkdir(parents=True)
            (state_dir / "sprint.lock").write_text("12345")

            # Mock discover_project_root to return our temp directory
            with patch(
                "claudesprint.services.path_service.PathService.discover_project_root",
                return_value=project_root,
            ):
                # Input that should be blocked (watch command)
                json_input = '{"tool_input":{"command":"npm test --watch"}}'
                result = runner.invoke(
                    app,
                    ["hook", "--type", "server-guard"],
                    input=json_input,
                )

                # Should exit 2 (block) because session is active and command is blocked
                assert result.exit_code == 2

    def test_hook_allows_safe_command_when_session_active(self) -> None:
        """Test that hook allows safe commands when session is active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            # Create sprint.lock to indicate active session
            state_dir = project_root / ".claudesprint" / "state"
            state_dir.mkdir(parents=True)
            (state_dir / "sprint.lock").write_text("12345")

            # Mock discover_project_root to return our temp directory
            with patch(
                "claudesprint.services.path_service.PathService.discover_project_root",
                return_value=project_root,
            ):
                # Input that should be allowed (normal command)
                json_input = '{"tool_input":{"command":"npm test"}}'
                result = runner.invoke(
                    app,
                    ["hook", "--type", "server-guard"],
                    input=json_input,
                )

                # Should exit 0 (allow) - command is safe
                assert result.exit_code == 0
