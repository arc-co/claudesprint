"""Hook command for Claude Code hooks.

This module needs fast startup since hooks are called frequently.
"""

from typing import Annotated

import typer

from claudesprint.commands._shared import console, error


def run_hook(
    hook_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Hook type: server-guard, browser-guard, autonomous-continue"),
    ],
) -> None:
    """Execute a Claude hook handler.

    This command is called by Claude Code hooks configured in .claude/settings.json.
    It reads JSON input from stdin and exits with:
    - 0: Allow the operation
    - 2: Block the operation

    Example:
        echo '{"tool_input":{"command":"npm test"}}' | claudesprint hook --type server-guard
    """
    # Lazy import for fast startup when no active session
    from claudesprint.services.session_state import is_session_active

    # Early exit if no active session - allow manual Claude usage
    if not is_session_active():
        raise typer.Exit(0)

    # Only import heavy modules after session check
    from claudesprint.services.claude_hook_service import (
        ClaudeHookService,
        HookInput,
        HookType,
    )

    # Validate hook type
    try:
        hook_type_enum = HookType(hook_type)
    except ValueError:
        valid_types = ", ".join(t.value for t in list(HookType))
        console.print(error(f"Invalid hook type: {hook_type}"))
        console.print(f"Valid types: {valid_types}")
        raise typer.Exit(1) from None

    # Parse input from stdin
    hook_input = HookInput.from_stdin()

    # Execute hook
    service = ClaudeHookService()
    result = service.execute_hook(hook_type_enum, hook_input)

    # Exit with appropriate code
    raise typer.Exit(result.value)
