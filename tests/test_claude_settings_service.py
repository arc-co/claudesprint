"""Tests for ClaudeSettingsService."""

import json
import tempfile
from pathlib import Path

from claudesprint.services.claude_settings_service import (
    ClaudeSettingsService,
    HookInjectionResult,
)


class TestClaudeSettingsServiceBasics:
    """Tests for basic ClaudeSettingsService functionality."""

    def test_settings_exist_returns_false_when_missing(self) -> None:
        """Test settings_exist returns False when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            assert service.settings_exist() is False

    def test_settings_exist_returns_true_when_present(self) -> None:
        """Test settings_exist returns True when file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text("{}")

            service = ClaudeSettingsService(tmpdir)
            assert service.settings_exist() is True

    def test_read_settings_returns_none_when_missing(self) -> None:
        """Test read_settings returns None when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            assert service.read_settings() is None

    def test_read_settings_parses_valid_json(self) -> None:
        """Test read_settings parses valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text('{"key": "value"}')

            service = ClaudeSettingsService(tmpdir)
            settings = service.read_settings()

            assert settings == {"key": "value"}

    def test_read_settings_returns_none_for_invalid_json(self) -> None:
        """Test read_settings returns None for invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text("not valid json")

            service = ClaudeSettingsService(tmpdir)
            assert service.read_settings() is None

    def test_write_settings_creates_file(self) -> None:
        """Test write_settings creates the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            success = service.write_settings({"key": "value"})

            assert success is True
            settings_path = Path(tmpdir) / ".claude" / "settings.json"
            assert settings_path.exists()
            assert json.loads(settings_path.read_text()) == {"key": "value"}

    def test_write_settings_creates_claude_directory(self) -> None:
        """Test write_settings creates .claude/ directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            service.write_settings({})

            claude_dir = Path(tmpdir) / ".claude"
            assert claude_dir.is_dir()


class TestBackupSettings:
    """Tests for backup functionality."""

    def test_backup_settings_creates_backup(self) -> None:
        """Test backup_settings creates a backup file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            settings_path = claude_dir / "settings.json"
            settings_path.write_text('{"original": true}')

            service = ClaudeSettingsService(tmpdir)
            backup_path = service.backup_settings()

            assert backup_path is not None
            backup = Path(backup_path)
            assert backup.exists()
            assert json.loads(backup.read_text()) == {"original": True}

    def test_backup_settings_returns_none_when_no_file(self) -> None:
        """Test backup_settings returns None when no file to backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            assert service.backup_settings() is None


class TestInjectHooks:
    """Tests for hook injection."""

    def test_inject_hooks_creates_new_settings(self) -> None:
        """Test inject_hooks creates settings.json when missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            result = service.inject_hooks()

            assert result.success is True
            assert service.settings_exist()
            settings = service.read_settings()
            assert "hooks" in settings

    def test_inject_hooks_adds_claudesprint_hooks(self) -> None:
        """Test inject_hooks adds the expected hook entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            result = service.inject_hooks()

            assert result.success is True
            settings = service.read_settings()
            hooks = settings["hooks"]

            # Check PreToolUse hooks
            assert "PreToolUse" in hooks
            pre_tool_use = hooks["PreToolUse"]
            matchers = [h.get("matcher") for h in pre_tool_use]
            assert "Bash" in matchers
            assert "Skill" in matchers

            # Check Stop hooks
            assert "Stop" in hooks

    def test_inject_hooks_preserves_user_hooks(self) -> None:
        """Test inject_hooks preserves existing user-defined hooks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing settings with user hooks
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            existing = {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Read",
                            "hooks": [{"type": "command", "command": "my-custom-hook"}],
                        }
                    ]
                }
            }
            (claude_dir / "settings.json").write_text(json.dumps(existing))

            service = ClaudeSettingsService(tmpdir)
            result = service.inject_hooks()

            assert result.success is True
            settings = service.read_settings()
            hooks = settings["hooks"]["PreToolUse"]

            # User hook should still be present
            matchers = [h.get("matcher") for h in hooks]
            assert "Read" in matchers

            # ClaudeSprint hooks should also be present
            assert "Bash" in matchers

    def test_inject_hooks_replaces_existing_claudesprint_hooks(self) -> None:
        """Test inject_hooks replaces existing claudesprint hooks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing settings with old claudesprint hooks
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            existing = {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {"type": "command", "command": "claudesprint hook --type old-hook"}
                            ],
                        }
                    ]
                }
            }
            (claude_dir / "settings.json").write_text(json.dumps(existing))

            service = ClaudeSettingsService(tmpdir)
            result = service.inject_hooks()

            assert result.success is True
            settings = service.read_settings()
            hooks = settings["hooks"]["PreToolUse"]

            # Should have exactly one Bash matcher (not duplicated)
            bash_hooks = [h for h in hooks if h.get("matcher") == "Bash"]
            assert len(bash_hooks) == 1

            # Should have the new hook command
            bash_hook = bash_hooks[0]
            assert "server-guard" in bash_hook["hooks"][0]["command"]

    def test_inject_hooks_creates_backup(self) -> None:
        """Test inject_hooks creates backup of existing settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text('{"existing": true}')

            service = ClaudeSettingsService(tmpdir)
            result = service.inject_hooks()

            assert result.success is True
            assert result.backup_path is not None
            assert Path(result.backup_path).exists()

    def test_inject_hooks_skips_invalid_json(self) -> None:
        """Test inject_hooks skips injection when settings has invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text("not valid json")

            service = ClaudeSettingsService(tmpdir)
            result = service.inject_hooks()

            assert result.success is False
            assert "Invalid JSON" in result.error

    def test_inject_hooks_lists_added_hooks(self) -> None:
        """Test inject_hooks lists what hooks were added."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            result = service.inject_hooks()

            assert result.success is True
            assert len(result.hooks_added) == 3
            assert any("server-guard" in h for h in result.hooks_added)
            assert any("browser-guard" in h for h in result.hooks_added)
            assert any("autonomous-continue" in h for h in result.hooks_added)


class TestRemoveHooks:
    """Tests for hook removal."""

    def test_remove_hooks_removes_claudesprint_hooks(self) -> None:
        """Test remove_hooks removes claudesprint hooks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            service.inject_hooks()

            success = service.remove_hooks()

            assert success is True
            service.read_settings()
            assert not service.has_claudesprint_hooks()

    def test_remove_hooks_preserves_user_hooks(self) -> None:
        """Test remove_hooks preserves user hooks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create settings with both claudesprint and user hooks
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            settings = {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "claudesprint hook --type server-guard"}],
                        },
                        {
                            "matcher": "Read",
                            "hooks": [{"type": "command", "command": "my-user-hook"}],
                        },
                    ]
                }
            }
            (claude_dir / "settings.json").write_text(json.dumps(settings))

            service = ClaudeSettingsService(tmpdir)
            success = service.remove_hooks()

            assert success is True
            settings = service.read_settings()
            hooks = settings["hooks"]["PreToolUse"]

            # User hook should remain
            assert len(hooks) == 1
            assert hooks[0]["matcher"] == "Read"

    def test_remove_hooks_succeeds_when_no_settings(self) -> None:
        """Test remove_hooks succeeds when no settings file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            success = service.remove_hooks()
            assert success is True


class TestHasClaudesprintHooks:
    """Tests for has_claudesprint_hooks."""

    def test_has_claudesprint_hooks_returns_false_when_no_settings(self) -> None:
        """Test returns False when no settings file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            assert service.has_claudesprint_hooks() is False

    def test_has_claudesprint_hooks_returns_true_when_present(self) -> None:
        """Test returns True when claudesprint hooks are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ClaudeSettingsService(tmpdir)
            service.inject_hooks()
            assert service.has_claudesprint_hooks() is True

    def test_has_claudesprint_hooks_returns_false_for_user_hooks(self) -> None:
        """Test returns False when only user hooks are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            settings = {
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Bash", "hooks": [{"type": "command", "command": "my-hook"}]}
                    ]
                }
            }
            (claude_dir / "settings.json").write_text(json.dumps(settings))

            service = ClaudeSettingsService(tmpdir)
            assert service.has_claudesprint_hooks() is False


class TestHookInjectionResult:
    """Tests for HookInjectionResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values."""
        result = HookInjectionResult(success=True)

        assert result.success is True
        assert result.backup_path is None
        assert result.error is None
        assert result.hooks_added == []
        assert result.warnings == []

    def test_with_values(self) -> None:
        """Test with all values set."""
        result = HookInjectionResult(
            success=False,
            backup_path="/path/to/backup",
            error="Something went wrong",
            hooks_added=["hook1", "hook2"],
            warnings=["warning1"],
        )

        assert result.success is False
        assert result.backup_path == "/path/to/backup"
        assert result.error == "Something went wrong"
        assert result.hooks_added == ["hook1", "hook2"]
        assert result.warnings == ["warning1"]
