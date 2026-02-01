"""Service for handling Claude hook logic.

This module implements the hook handlers that run as PreToolUse and Stop hooks
for Claude Code, replacing bash script hooks with portable Python implementations.
"""

import json
import shlex
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


@dataclass
class CommandRule:
    """Rule for detecting blocked commands."""

    required_sequence: tuple[str, ...]  # e.g., ("git", "commit")
    blocked_flags: frozenset[str] = frozenset()  # Flags that trigger block
    allow_flags: frozenset[str] = frozenset()  # Flags that allow if present
    block_without_allow_flags: bool = False  # Block when allow_flags absent


# Rules for interactive git commands (token-based parsing for complex flag logic)
# Each rule defines a command sequence and flag conditions that trigger blocking.
GIT_INTERACTIVE_RULES = [
    CommandRule(
        required_sequence=("git", "rebase"),
        blocked_flags=frozenset({"-i", "--interactive"}),
    ),
    CommandRule(
        required_sequence=("git", "add"),
        blocked_flags=frozenset({"-i", "--interactive", "-p", "--patch"}),
    ),
    # Block git commit unless it has a flag that provides a message non-interactively.
    # Without -m, -F, -C, or --no-edit, git commit opens an editor for the message.
    CommandRule(
        required_sequence=("git", "commit"),
        allow_flags=frozenset(
            {"-m", "--message", "-F", "--file", "-C", "--reuse-message", "--no-edit"}
        ),
        block_without_allow_flags=True,
    ),
]


class ClaudeHookService:
    """Service for executing Claude hook logic."""

    # Commands that block the terminal waiting for input or run indefinitely.
    # Note: We intentionally don't include `-w` as it's ambiguous (e.g., jest -w
    # sets worker count, not watch mode). Only explicit --watch is blocked.
    WATCH_PATTERNS = [
        r"\bwatch\b",
        r"--watch\b",
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

    # Server commands that run indefinitely. These patterns are used for DETECTION only.
    # Server commands are ALLOWED (not blocked) - the model is instructed via prompts to
    # check if a server is already running before starting one.
    # See _project_discovery.xml.j2 <server_management> section.
    SERVER_PATTERNS = [
        # Node.js package manager dev commands
        r"\bnpm\s+run\s+dev\b",
        r"\bnpm\s+run\s+start\b",
        r"\byarn\s+dev\b",
        r"\byarn\s+start\b",
        r"\byarn\s+run\s+dev\b",
        r"\bpnpm\s+dev\b",
        r"\bpnpm\s+run\s+dev\b",
        r"\bpnpm\s+start\b",
        r"\bbun\s+dev\b",
        r"\bbun\s+run\s+dev\b",
        # Python web servers
        r"\bpython\s+-m\s+http\.server\b",
        r"\bpython3\s+-m\s+http\.server\b",
        r"\bpython\s+.*\s+runserver\b",  # Django
        r"\bpython3\s+.*\s+runserver\b",
        r"\buvicorn\b",  # FastAPI/Starlette
        r"\bgunicorn\b",
        r"\bflask\s+run\b",
        r"\bpoetry\s+run\s+.*runserver\b",
        r"\buv\s+run\s+.*runserver\b",
        # Generic server commands
        r"\bnode\s+.*server",
        r"\bnpx\s+.*serve\b",
        r"\bnpx\s+vite\b",
        r"\bnpx\s+next\s+dev\b",
        # Rust/Go servers
        r"\bcargo\s+run\b.*--bin\s+.*server",
        r"\bgo\s+run\b.*server",
    ]

    def __init__(self) -> None:
        """Initialize the hook service."""
        import re

        self._watch_regex = [re.compile(p, re.IGNORECASE) for p in self.WATCH_PATTERNS]
        self._git_regex = [
            re.compile(p, re.IGNORECASE) for p in self.INTERACTIVE_GIT_PATTERNS
        ]
        self._server_regex = [
            re.compile(p, re.IGNORECASE) for p in self.SERVER_PATTERNS
        ]

    def _tokenize_command(self, command: str) -> list[str] | None:
        """Tokenize a command using shlex.

        Args:
            command: The command string to tokenize

        Returns:
            List of tokens, or None on parse failure (e.g., unclosed quotes)
        """
        if not command:
            return []
        try:
            return shlex.split(command)
        except ValueError:
            return None

    def _contains_sequence(
        self,
        tokens: list[str],
        sequence: tuple[str, ...],
    ) -> bool:
        """Check if tokens contain sequence in order, starting at first token.

        Args:
            tokens: List of command tokens
            sequence: Tuple of strings that must appear in order

        Returns:
            True if sequence found in order within tokens, starting at index 0
        """
        if not sequence:
            return True
        if not tokens:
            return False

        seq_idx = 0
        for i, token in enumerate(tokens):
            if token.lower() == sequence[seq_idx].lower():
                seq_idx += 1
                if seq_idx == len(sequence):
                    return True
            elif i == 0:
                # First element of sequence must match first token
                return False
        return False

    def _has_any_flag(self, tokens: list[str], flags: frozenset[str]) -> bool:
        """Check if any flag appears in tokens.

        Flags are matched case-sensitively (e.g., -m != -M) since CLI flags
        are case-sensitive. Also handles:
        - --flag=value syntax for long flags (e.g., --message="foo")
        - Combined short flags (e.g., -am contains -a and -m)

        Args:
            tokens: List of command tokens
            flags: Set of flags to look for

        Returns:
            True if any flag found in tokens
        """
        for token in tokens:
            if token in flags:
                return True
            # Handle --flag=value syntax (e.g., --message="foo")
            if "=" in token:
                flag_part = token.split("=", 1)[0]
                if flag_part in flags:
                    return True
            # Handle combined short flags (e.g., -am contains -a and -m)
            if token.startswith("-") and not token.startswith("--") and len(token) > 2:
                for char in token[1:]:
                    if f"-{char}" in flags:
                        return True
        return False

    def _matches_rule(self, tokens: list[str], rule: CommandRule) -> bool:
        """Check if tokens match a command rule.

        Args:
            tokens: List of command tokens
            rule: CommandRule to check against

        Returns:
            True if the tokens match the rule
        """
        # Check required sequence first
        if rule.required_sequence and not self._contains_sequence(
            tokens, rule.required_sequence
        ):
            return False

        # If blocked_flags specified and present, block
        if rule.blocked_flags and self._has_any_flag(tokens, rule.blocked_flags):
            return True

        # If block_without_allow_flags and no allow_flags present, block
        return bool(rule.block_without_allow_flags and not self._has_any_flag(tokens, rule.allow_flags))

    def _strip_quoted_content(self, command: str) -> str:
        """Remove content inside quotes to avoid matching args/messages.

        Uses Python's shlex module for robust shell parsing that handles:
        - Double quotes with backslash escapes (e.g., \\" for literal quote)
        - Single quotes (literal content, no escaping per POSIX)
        - Command substitutions with nested quotes
        - Other complex shell quoting edge cases

        This prevents false positives where blocked patterns appear inside
        quoted strings (e.g., commit messages, echo statements).

        Examples:
            'git commit -m "watch out for bugs"' -> 'git commit -m ""'
            'echo "v1.0 \\"watch\\" release"' -> 'echo ""'
            'echo "$(git commit -m 'watch')"' -> 'echo ""'

        Args:
            command: The command string to process

        Returns:
            Command with quoted content replaced by empty quotes
        """
        if not command:
            return command

        result: list[str] = []
        i = 0
        n = len(command)

        while i < n:
            char = command[i]

            if char in ('"', "'"):
                # Use shlex to find the end of this quoted string
                try:
                    # Create a POSIX-mode lexer for the remaining string
                    lexer = shlex.shlex(command[i:], posix=True)
                    # Get one token (the quoted string content)
                    token = lexer.get_token()

                    if token is not None:
                        # Calculate how many characters were consumed
                        # by reading what remains in the stream
                        remaining = lexer.instream.read()
                        consumed = len(command) - i - len(remaining)
                        result.append('""')
                        i += consumed
                        continue
                except ValueError:
                    # Parse error (e.g., unterminated quote)
                    # Fall through to manual handling for graceful degradation
                    pass

                # Fallback for parse errors: use simple state machine
                quote_char = char
                result.append('""')
                i += 1
                if quote_char == '"':
                    # Handle double quotes with escapes
                    while i < n:
                        if command[i] == "\\" and i + 1 < n:
                            i += 2  # Skip escape sequence
                        elif command[i] == '"':
                            i += 1  # Skip closing quote
                            break
                        else:
                            i += 1
                else:
                    # Handle single quotes (no escaping)
                    while i < n and command[i] != "'":
                        i += 1
                    if i < n:
                        i += 1  # Skip closing quote
            else:
                result.append(char)
                i += 1

        return "".join(result)

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
        - Server commands that may conflict with existing servers or run indefinitely

        Args:
            hook_input: Parsed hook input

        Returns:
            HookResult.BLOCK if command should be blocked, ALLOW otherwise
        """
        tool_input = hook_input.tool_input or {}
        command = tool_input.get("command", "")

        if not command:
            return HookResult.ALLOW

        # Check for watch patterns using regex on quote-stripped content
        if self.is_watch_command(command):
            self._print_block_message(
                f"Blocked watch command: {command[:50]}..."
                if len(command) > 50
                else f"Blocked watch command: {command}"
            )
            return HookResult.BLOCK

        # Check for interactive git patterns using token-based parsing
        if self.is_interactive_git_command(command):
            self._print_block_message(
                f"Blocked interactive git command: {command[:50]}..."
                if len(command) > 50
                else f"Blocked interactive git command: {command}"
            )
            return HookResult.BLOCK

        # Note: Server commands (npm run dev, etc.) are intentionally ALLOWED.
        # The prompt instructs the model to check if a server is already running
        # before starting one, to prevent duplicate spawning and memory exhaustion.
        # See _project_discovery.xml.j2 <server_management> section.

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

        Uses regex on quote-stripped content to avoid false positives from
        watch-like words appearing in quoted strings (e.g., commit messages).

        Args:
            command: The command string to check

        Returns:
            True if the command would block waiting for input
        """
        stripped = self._strip_quoted_content(command)
        return any(pattern.search(stripped) for pattern in self._watch_regex)

    def is_interactive_git_command(self, command: str) -> bool:
        """Check if a command is an interactive git command.

        Uses token-based parsing for accuracy, with regex fallback for
        malformed commands (e.g., unclosed quotes).

        Args:
            command: The command string to check

        Returns:
            True if the command requires interactive input
        """
        tokens = self._tokenize_command(command)
        if tokens is None:
            # Fallback to regex for malformed commands
            stripped = self._strip_quoted_content(command)
            return any(pattern.search(stripped) for pattern in self._git_regex)
        return any(self._matches_rule(tokens, rule) for rule in GIT_INTERACTIVE_RULES)

    def is_server_command(self, command: str) -> bool:
        """Check if a command starts a server.

        Uses regex on quote-stripped content to avoid false positives from
        server-like words appearing in quoted strings (e.g., commit messages).

        Args:
            command: The command string to check

        Returns:
            True if the command starts a server
        """
        stripped = self._strip_quoted_content(command)
        return any(pattern.search(stripped) for pattern in self._server_regex)
