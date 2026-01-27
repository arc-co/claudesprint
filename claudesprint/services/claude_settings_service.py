"""Service for managing .claude/settings.json hook configuration.

This module handles injecting and removing ClaudeSprint hooks from the
Claude Code settings file while preserving user-defined hooks.
"""

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Hook configuration to inject into settings.json
CLAUDESPRINT_HOOKS: dict[str, Any] = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": "claudesprint hook --type server-guard",
                        "timeout": 5,
                    }
                ],
            },
            {
                "matcher": "Skill",
                "hooks": [
                    {
                        "type": "command",
                        "command": "claudesprint hook --type browser-guard",
                        "timeout": 10,
                    }
                ],
            },
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "claudesprint hook --type autonomous-continue",
                        "timeout": 5,
                    }
                ],
            }
        ],
    }
}

# Marker to identify claudesprint-managed hooks
CLAUDESPRINT_HOOK_MARKER = "claudesprint hook"


@dataclass
class HookInjectionResult:
    """Result of hook injection operation."""

    success: bool
    backup_path: str | None = None
    error: str | None = None
    hooks_added: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ClaudeSettingsService:
    """Service for managing .claude/settings.json."""

    CLAUDE_DIR = ".claude"
    SETTINGS_FILE = "settings.json"
    BACKUP_SUFFIX = ".backup"

    def __init__(self, project_root: str | Path) -> None:
        """Initialize the service.

        Args:
            project_root: Path to the project root directory
        """
        self.project_root = Path(project_root)
        self.claude_dir = self.project_root / self.CLAUDE_DIR
        self.settings_path = self.claude_dir / self.SETTINGS_FILE
        self.backup_path = self.claude_dir / f"{self.SETTINGS_FILE}{self.BACKUP_SUFFIX}"

    def settings_exist(self) -> bool:
        """Check if settings.json exists.

        Returns:
            True if the settings file exists
        """
        return self.settings_path.exists()

    def read_settings(self) -> dict[str, Any] | None:
        """Read the current settings.json.

        Returns:
            Parsed settings dict, or None if file doesn't exist or is invalid
        """
        if not self.settings_exist():
            return None

        try:
            content = self.settings_path.read_text()
            result: dict[str, Any] = json.loads(content)
            return result
        except (json.JSONDecodeError, OSError):
            return None

    def write_settings(self, settings: dict[str, Any]) -> bool:
        """Write settings to settings.json.

        Args:
            settings: Settings dict to write

        Returns:
            True if write succeeded
        """
        try:
            # Ensure .claude/ directory exists
            self.claude_dir.mkdir(parents=True, exist_ok=True)
            content = json.dumps(settings, indent=2)
            self.settings_path.write_text(content + "\n")
            return True
        except OSError:
            return False

    def backup_settings(self) -> str | None:
        """Create a backup of the current settings.json.

        Returns:
            Path to backup file, or None if backup failed or no file to backup
        """
        if not self.settings_exist():
            return None

        try:
            shutil.copy2(self.settings_path, self.backup_path)
            return str(self.backup_path)
        except OSError:
            return None

    def inject_hooks(self) -> HookInjectionResult:
        """Inject ClaudeSprint hooks into settings.json.

        This method:
        1. Creates .claude/ directory if needed
        2. Backs up existing settings.json if it exists
        3. Merges ClaudeSprint hooks with existing hooks
        4. Preserves user-defined hooks that don't conflict

        Returns:
            HookInjectionResult with operation details
        """
        result = HookInjectionResult(success=True)

        # Read existing settings or start with empty dict
        existing_settings = self.read_settings()

        if existing_settings is None and self.settings_exist():
            # File exists but is invalid JSON
            result.warnings.append(
                f"Existing {self.SETTINGS_FILE} contains invalid JSON, skipping hook injection"
            )
            result.success = False
            result.error = "Invalid JSON in existing settings.json"
            return result

        # Backup if settings exist
        if existing_settings is not None:
            backup_path = self.backup_settings()
            if backup_path:
                result.backup_path = backup_path

        # Start with existing settings or empty dict
        settings = existing_settings or {}

        # Merge hooks
        merged_hooks = self._merge_hooks(
            settings.get("hooks", {}), CLAUDESPRINT_HOOKS["hooks"]
        )
        settings["hooks"] = merged_hooks

        # Track what was added
        result.hooks_added = ["server-guard (PreToolUse:Bash)",
                             "browser-guard (PreToolUse:Skill)",
                             "autonomous-continue (Stop)"]

        # Write updated settings
        if not self.write_settings(settings):
            result.success = False
            result.error = "Failed to write settings.json"
            return result

        return result

    def remove_hooks(self) -> bool:
        """Remove ClaudeSprint hooks from settings.json.

        Returns:
            True if hooks were removed successfully
        """
        settings = self.read_settings()
        if settings is None:
            return True  # Nothing to remove

        hooks = settings.get("hooks", {})
        if not hooks:
            return True

        # Remove claudesprint hooks from each event type
        cleaned_hooks: dict[str, Any] = {}
        for event_type, event_hooks in hooks.items():
            if isinstance(event_hooks, list):
                cleaned = self._remove_claudesprint_hooks_from_list(event_hooks)
                if cleaned:
                    cleaned_hooks[event_type] = cleaned

        settings["hooks"] = cleaned_hooks
        return self.write_settings(settings)

    def has_claudesprint_hooks(self) -> bool:
        """Check if settings.json contains ClaudeSprint hooks.

        Returns:
            True if any ClaudeSprint hooks are present
        """
        settings = self.read_settings()
        if settings is None:
            return False

        hooks = settings.get("hooks", {})
        for event_hooks in hooks.values():
            if isinstance(event_hooks, list):
                for hook_entry in event_hooks:
                    if self._is_claudesprint_hook_entry(hook_entry):
                        return True
        return False

    def _merge_hooks(
        self, existing: dict[str, Any], new: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge new hooks with existing hooks, replacing claudesprint hooks.

        Args:
            existing: Existing hooks configuration
            new: New hooks to merge in

        Returns:
            Merged hooks configuration
        """
        result = {}

        # Process all event types from both existing and new
        all_event_types = set(existing.keys()) | set(new.keys())

        for event_type in all_event_types:
            existing_hooks = existing.get(event_type, [])
            new_hooks = new.get(event_type, [])

            if not isinstance(existing_hooks, list):
                existing_hooks = []
            if not isinstance(new_hooks, list):
                new_hooks = []

            # Remove existing claudesprint hooks
            filtered_existing = self._remove_claudesprint_hooks_from_list(
                existing_hooks
            )

            # Merge: new hooks first (claudesprint), then existing user hooks
            result[event_type] = new_hooks + filtered_existing

        return result

    def _remove_claudesprint_hooks_from_list(
        self, hooks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove ClaudeSprint hooks from a list of hook entries.

        Args:
            hooks: List of hook entry dicts

        Returns:
            Filtered list without ClaudeSprint hooks
        """
        return [h for h in hooks if not self._is_claudesprint_hook_entry(h)]

    def _is_claudesprint_hook_entry(self, hook_entry: dict[str, Any]) -> bool:
        """Check if a hook entry is a ClaudeSprint hook.

        Args:
            hook_entry: A hook entry dict (may have 'matcher' and 'hooks' keys)

        Returns:
            True if this is a ClaudeSprint hook entry
        """
        # Check the 'hooks' list within the entry
        inner_hooks = hook_entry.get("hooks", [])
        if isinstance(inner_hooks, list):
            for hook in inner_hooks:
                command = hook.get("command", "")
                if isinstance(command, str) and CLAUDESPRINT_HOOK_MARKER in command:
                    return True
        return False
