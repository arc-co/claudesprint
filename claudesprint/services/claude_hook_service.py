"""Service for handling Claude hook logic.

This module implements the hook handlers that run as PreToolUse and Stop hooks
for Claude Code, replacing bash script hooks with portable Python implementations.
"""

import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any


class HookType(str, Enum):
    """Types of hooks that can be executed."""

    SERVER_GUARD = "server-guard"
    BROWSER_GUARD = "browser-guard"
    AUTONOMOUS_CONTINUE = "autonomous-continue"


class HookResult(int, Enum):
    """Hook exit codes matching Claude hook protocol."""

    ALLOW = 0  # Allow the tool call to proceed
    BLOCK = 2  # Block the tool call


@dataclass
class HookInput:
    """Parsed hook input from stdin."""

    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    session_id: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_stdin(cls) -> "HookInput":
        """Parse hook input from stdin JSON.

        Returns:
            HookInput with parsed data, or empty HookInput on parse failure
        """
        try:
            raw = sys.stdin.read()
            if not raw.strip():
                return cls()
            data = json.loads(raw)
            return cls(
                tool_name=data.get("tool_name"),
                tool_input=data.get("tool_input", {}),
                session_id=data.get("session_id"),
                raw_data=data,
            )
        except (json.JSONDecodeError, OSError):
            return cls()


class ClaudeHookService:
    """Service for executing Claude hook logic."""

    # Commands that block the terminal waiting for input or run indefinitely
    WATCH_PATTERNS = [
        r"\bwatch\b",
        r"--watch\b",
        r"-w\s*$",  # Common watch flag at end
        r"\bnpm\s+start\b",  # Often runs a dev server
        r"\byarn\s+start\b",
        r"\bserve\b",
        r"\btail\s+-f\b",
        r"\btail\s+--follow\b",
    ]

    # Interactive git commands that require user input
    INTERACTIVE_GIT_PATTERNS = [
        r"\bgit\s+rebase\s+-i\b",
        r"\bgit\s+rebase\s+--interactive\b",
        r"\bgit\s+add\s+-i\b",
        r"\bgit\s+add\s+--interactive\b",
        r"\bgit\s+add\s+-p\b",
        r"\bgit\s+add\s+--patch\b",
        r"\bgit\s+commit\s+--amend\s*$",  # Without -m, opens editor
        r"\bgit\s+commit\s*$",  # Without -m, opens editor
    ]

    # Server commands that may conflict with existing servers
    SERVER_PATTERNS = [
        r"\bnpm\s+run\s+dev\b",
        r"\bnpm\s+run\s+start\b",
        r"\byarn\s+dev\b",
        r"\byarn\s+start\b",
        r"\bpython\s+-m\s+http\.server\b",
        r"\bpython\s+.*\s+runserver\b",
        r"\bnode\s+.*server",
        r"\bnpx\s+.*serve\b",
    ]

    # Regex patterns for stripping quoted content
    _SINGLE_QUOTE_PATTERN = re.compile(r"'[^']*'")
    _DOUBLE_QUOTE_PATTERN = re.compile(r'"[^"]*"')

    def __init__(self) -> None:
        """Initialize the hook service."""
        self._watch_regex = [re.compile(p, re.IGNORECASE) for p in self.WATCH_PATTERNS]
        self._git_regex = [
            re.compile(p, re.IGNORECASE) for p in self.INTERACTIVE_GIT_PATTERNS
        ]
        self._server_regex = [
            re.compile(p, re.IGNORECASE) for p in self.SERVER_PATTERNS
        ]

    def _strip_quoted_content(self, command: str) -> str:
        """Remove content inside quotes to avoid matching args/messages.

        This prevents false positives where blocked patterns appear inside
        quoted strings (e.g., commit messages, echo statements).

        Example:
            'git commit -m "watch out for bugs"' -> 'git commit -m ""'

        Args:
            command: The command string to process

        Returns:
            Command with quoted content replaced by empty quotes
        """
        # Replace single-quoted strings with empty quotes
        result = self._SINGLE_QUOTE_PATTERN.sub('""', command)
        # Replace double-quoted strings with empty quotes
        result = self._DOUBLE_QUOTE_PATTERN.sub('""', result)
        return result

    def execute_hook(self, hook_type: HookType, hook_input: HookInput) -> HookResult:
        """Execute the specified hook type.

        Args:
            hook_type: The type of hook to execute
            hook_input: Parsed input from stdin

        Returns:
            HookResult indicating whether to allow or block
        """
        if hook_type == HookType.SERVER_GUARD:
            return self._server_guard(hook_input)
        elif hook_type == HookType.BROWSER_GUARD:
            return self._browser_guard(hook_input)
        elif hook_type == HookType.AUTONOMOUS_CONTINUE:
            return self._autonomous_continue(hook_input)
        else:
            # Unknown hook type, allow by default
            return HookResult.ALLOW

    def _server_guard(self, hook_input: HookInput) -> HookResult:
        """Guard against commands that block the terminal or run indefinitely.

        Blocks:
        - Watch commands (--watch, npm test --watch, etc.)
        - Interactive git commands (git rebase -i, git add -p, etc.)
        - Server commands that may conflict with existing servers

        Args:
            hook_input: Parsed hook input

        Returns:
            HookResult.BLOCK if command should be blocked, ALLOW otherwise
        """
        tool_input = hook_input.tool_input or {}
        command = tool_input.get("command", "")

        if not command:
            return HookResult.ALLOW

        # Strip quoted content to avoid false positives on commit messages, etc.
        # e.g., 'git commit -m "watch out"' should not be blocked
        command_for_matching = self._strip_quoted_content(command)

        # Check for watch patterns
        for pattern in self._watch_regex:
            if pattern.search(command_for_matching):
                self._print_block_message(
                    f"Blocked watch command: {command[:50]}..."
                    if len(command) > 50
                    else f"Blocked watch command: {command}"
                )
                return HookResult.BLOCK

        # Check for interactive git patterns
        for pattern in self._git_regex:
            if pattern.search(command_for_matching):
                self._print_block_message(
                    f"Blocked interactive git command: {command[:50]}..."
                    if len(command) > 50
                    else f"Blocked interactive git command: {command}"
                )
                return HookResult.BLOCK

        return HookResult.ALLOW

    def _browser_guard(self, hook_input: HookInput) -> HookResult:  # noqa: ARG002
        """Guard for browser/skill operations.

        Currently a placeholder that always allows operations.
        Can be extended to:
        - Clean orphan browser processes
        - Check disk/memory usage
        - Validate skill parameters

        Args:
            hook_input: Parsed hook input

        Returns:
            HookResult.ALLOW (placeholder implementation)
        """
        # Placeholder - always allow for now
        # Future: Add browser process cleanup, resource checks
        return HookResult.ALLOW

    def _autonomous_continue(self, hook_input: HookInput) -> HookResult:  # noqa: ARG002
        """Guard for Stop events to ensure workflow advances.

        Currently a placeholder that always allows the stop.
        Can be extended to:
        - Check if workflow step has advanced
        - Warn if stopping mid-step
        - Auto-save progress

        Args:
            hook_input: Parsed hook input

        Returns:
            HookResult.ALLOW (placeholder implementation)
        """
        # Placeholder - always allow stop for now
        # Future: Check workflow progress, save state
        return HookResult.ALLOW

    def _print_block_message(self, message: str) -> None:
        """Print a block message to stderr.

        Args:
            message: Message to print
        """
        print(f"[claudesprint] {message}", file=sys.stderr)

    def is_watch_command(self, command: str) -> bool:
        """Check if a command is a watch/blocking command.

        Quoted content is stripped before matching to avoid false positives.

        Args:
            command: The command string to check

        Returns:
            True if the command would block waiting for input
        """
        stripped = self._strip_quoted_content(command)
        return any(pattern.search(stripped) for pattern in self._watch_regex)

    def is_interactive_git_command(self, command: str) -> bool:
        """Check if a command is an interactive git command.

        Quoted content is stripped before matching to avoid false positives.

        Args:
            command: The command string to check

        Returns:
            True if the command requires interactive input
        """
        stripped = self._strip_quoted_content(command)
        return any(pattern.search(stripped) for pattern in self._git_regex)

    def is_server_command(self, command: str) -> bool:
        """Check if a command starts a server.

        Quoted content is stripped before matching to avoid false positives.

        Args:
            command: The command string to check

        Returns:
            True if the command starts a server
        """
        stripped = self._strip_quoted_content(command)
        return any(pattern.search(stripped) for pattern in self._server_regex)
