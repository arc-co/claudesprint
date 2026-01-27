"""Tool functions for Claude agent - hook runner and issue tools."""

from claudesprint.tools.hook_runner import (
    run_hook,
    run_test_hook,
    run_lint_hook,
    run_build_hook,
    run_validate_hook,
    HookResult,
    HookRunner,
    HookConfigError,
)

from claudesprint.tools import issue_tools

__all__ = [
    # Hook runner
    "run_hook",
    "run_test_hook",
    "run_lint_hook",
    "run_build_hook",
    "run_validate_hook",
    "HookResult",
    "HookRunner",
    "HookConfigError",
    # Issue tools
    "issue_tools",
]
