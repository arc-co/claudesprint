#!/usr/bin/env python3
"""CLI for ClaudeSprint tools - allows Claude agents to use tool functions via bash.

Usage:
    claudesprint-tools issue get
    claudesprint-tools issue init <issue_id> [--step=STEP] [--goal=GOAL] [--sprint-path=PATH]
    claudesprint-tools issue update [--goal=GOAL] [--next-action=ACTION]
    claudesprint-tools issue step <step_name> [--goal=GOAL] [--next-action=ACTION]
    claudesprint-tools issue change <path> <summary>
    claudesprint-tools issue failure <message>
    claudesprint-tools issue clear-failures

    claudesprint-tools sprint available [--spec=SPEC_ID]
    claudesprint-tools sprint start <issue_id> [--spec=SPEC_ID]
    claudesprint-tools sprint details <issue_id> [--spec=SPEC_ID]

    claudesprint-tools test run
    claudesprint-tools test lint
    claudesprint-tools test build
    claudesprint-tools test validate
"""

import argparse
import json
from pathlib import Path


def find_project_root() -> Path:
    """Find the project root by looking for .claude directory."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".claude").exists():
            return current
        current = current.parent
    return Path.cwd()


def configure_tools():
    """Configure tool modules with project paths."""
    project_root = find_project_root()
    # Use .claudesprint/ directory (not .claude/) to match path_service.py and config.py
    project_dir = project_root / ".claudesprint" / "project"
    sprints_dir = project_root / ".claudesprint" / "sprints"

    from claudesprint.tools import issue_tools, hook_runner, sprint_tools

    issue_tools.configure(project_dir)
    sprint_tools.configure(sprints_dir)
    hook_runner.configure_runner(
        config_path=project_root / ".claudesprint" / "config" / "hooks.json",
        project_root=project_root,
    )


def cmd_issue_get(args):
    """Get current issue state."""
    from claudesprint.tools.issue_tools import get_issue

    result = get_issue()
    print(json.dumps(result.to_dict(), indent=2))


def cmd_issue_update(args):
    """Update issue fields."""
    from claudesprint.tools.issue_tools import update_issue

    result = update_issue(
        goal=args.goal,
        next_action=args.next_action,
    )
    print(json.dumps(result.to_dict(), indent=2))


def cmd_issue_step(args):
    """Set next workflow step."""
    from claudesprint.tools.issue_tools import set_next_step

    result = set_next_step(
        step=args.step,
        goal=args.goal,
        next_action=args.next_action,
        clear_failures=args.clear_failures,
    )
    print(json.dumps(result.to_dict(), indent=2))


def cmd_issue_change(args):
    """Record a file change."""
    from claudesprint.tools.issue_tools import record_change

    result = record_change(path=args.path, summary=args.summary)
    print(json.dumps(result.to_dict(), indent=2))


def cmd_issue_failure(args):
    """Record a failure."""
    from claudesprint.tools.issue_tools import record_failure

    result = record_failure(failure_message=args.message, increment_retry=not args.no_increment)
    print(json.dumps(result.to_dict(), indent=2))


def cmd_issue_clear_failures(args):
    """Clear failures and reset retry count."""
    from claudesprint.tools.issue_tools import clear_failures

    result = clear_failures()
    print(json.dumps(result.to_dict(), indent=2))


def cmd_issue_init(args):
    """Initialize current_issue.json for a selected issue."""
    from claudesprint.tools.issue_tools import init_issue

    result = init_issue(
        issue_id=args.issue_id,
        step=args.step,
        goal=args.goal,
        sprint_path=args.sprint_path,
    )
    print(json.dumps(result.to_dict(), indent=2))


def cmd_test_run(args):
    """Run test hook."""
    from claudesprint.tools.hook_runner import run_test_hook

    result = run_test_hook()
    print(json.dumps(result.to_dict(), indent=2))


def cmd_test_lint(args):
    """Run lint hook."""
    from claudesprint.tools.hook_runner import run_lint_hook

    result = run_lint_hook()
    print(json.dumps(result.to_dict(), indent=2))


def cmd_test_build(args):
    """Run build hook."""
    from claudesprint.tools.hook_runner import run_build_hook

    result = run_build_hook()
    print(json.dumps(result.to_dict(), indent=2))


def cmd_test_validate(args):
    """Run validate hook."""
    from claudesprint.tools.hook_runner import run_validate_hook

    result = run_validate_hook()
    print(json.dumps(result.to_dict(), indent=2))


def cmd_sprint_available(args):
    """List available issues in current sprint (token-optimized view)."""
    from claudesprint.tools.sprint_tools import list_available_issues

    result = list_available_issues(spec_id=args.spec)
    print(json.dumps(result.to_dict(), indent=2))


def cmd_sprint_start(args):
    """Mark an issue as in_progress (start working on it)."""
    from claudesprint.tools.sprint_tools import start_issue

    result = start_issue(issue_id=args.issue_id, spec_id=args.spec)
    print(json.dumps(result.to_dict(), indent=2))


def cmd_sprint_details(args):
    """Get full details for a specific issue."""
    from claudesprint.tools.sprint_tools import get_issue_details

    result = get_issue_details(issue_id=args.issue_id, spec_id=args.spec)
    print(json.dumps(result.to_dict(), indent=2))


def main():
    parser = argparse.ArgumentParser(description="ClaudeSprint tools CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Issue commands (replaces handoff)
    issue_parser = subparsers.add_parser("issue", help="Current issue management")
    issue_subparsers = issue_parser.add_subparsers(dest="subcommand", required=True)

    # issue get
    iget_parser = issue_subparsers.add_parser("get", help="Get issue state")
    iget_parser.set_defaults(func=cmd_issue_get)

    # issue update
    iupdate_parser = issue_subparsers.add_parser("update", help="Update issue fields")
    iupdate_parser.add_argument("--goal", help="New goal")
    iupdate_parser.add_argument("--next-action", help="New next action")
    iupdate_parser.set_defaults(func=cmd_issue_update)

    # issue step
    istep_parser = issue_subparsers.add_parser("step", help="Set next step")
    istep_parser.add_argument("step", help="Step name (implement, write-tests, etc.)")
    istep_parser.add_argument("--goal", help="New goal")
    istep_parser.add_argument("--next-action", help="New next action")
    istep_parser.add_argument("--clear-failures", action="store_true", help="Clear failures")
    istep_parser.set_defaults(func=cmd_issue_step)

    # issue change
    ichange_parser = issue_subparsers.add_parser("change", help="Record file change")
    ichange_parser.add_argument("path", help="File path")
    ichange_parser.add_argument("summary", help="Change summary")
    ichange_parser.set_defaults(func=cmd_issue_change)

    # issue failure
    ifail_parser = issue_subparsers.add_parser("failure", help="Record failure")
    ifail_parser.add_argument("message", help="Failure message")
    ifail_parser.add_argument("--no-increment", action="store_true", help="Don't increment retry")
    ifail_parser.set_defaults(func=cmd_issue_failure)

    # issue clear-failures
    iclear_parser = issue_subparsers.add_parser("clear-failures", help="Clear failures")
    iclear_parser.set_defaults(func=cmd_issue_clear_failures)

    # issue init
    iinit_parser = issue_subparsers.add_parser("init", help="Initialize issue state")
    iinit_parser.add_argument("issue_id", help="Issue ID to initialize")
    iinit_parser.add_argument("--step", default="read-docs", help="Initial step (default: read-docs)")
    iinit_parser.add_argument("--goal", help="Goal description")
    iinit_parser.add_argument("--sprint-path", help="Path to sprint.json")
    iinit_parser.set_defaults(func=cmd_issue_init)

    # Test commands
    test_parser = subparsers.add_parser("test", help="Test/validation hooks")
    test_subparsers = test_parser.add_subparsers(dest="subcommand", required=True)

    test_run_parser = test_subparsers.add_parser("run", help="Run tests")
    test_run_parser.set_defaults(func=cmd_test_run)

    test_lint_parser = test_subparsers.add_parser("lint", help="Run linter")
    test_lint_parser.set_defaults(func=cmd_test_lint)

    test_build_parser = test_subparsers.add_parser("build", help="Run build")
    test_build_parser.set_defaults(func=cmd_test_build)

    test_validate_parser = test_subparsers.add_parser("validate", help="Run all validation")
    test_validate_parser.set_defaults(func=cmd_test_validate)

    # Sprint commands (token-optimized views)
    sprint_parser = subparsers.add_parser("sprint", help="Sprint query tools")
    sprint_subparsers = sprint_parser.add_subparsers(dest="subcommand", required=True)

    # sprint available
    savail_parser = sprint_subparsers.add_parser(
        "available", help="List available issues (token-optimized)"
    )
    savail_parser.add_argument("--spec", help="Optional Spec ID to query")
    savail_parser.set_defaults(func=cmd_sprint_available)

    # sprint start
    sstart_parser = sprint_subparsers.add_parser(
        "start", help="Mark issue as in_progress"
    )
    sstart_parser.add_argument("issue_id", help="Issue ID to start")
    sstart_parser.add_argument("--spec", help="Optional Spec ID to query")
    sstart_parser.set_defaults(func=cmd_sprint_start)

    # sprint details
    sdetails_parser = sprint_subparsers.add_parser(
        "details", help="Get full issue details"
    )
    sdetails_parser.add_argument("issue_id", help="Issue ID to retrieve")
    sdetails_parser.add_argument("--spec", help="Optional Spec ID to query")
    sdetails_parser.set_defaults(func=cmd_sprint_details)

    args = parser.parse_args()

    # Configure tools with project paths
    configure_tools()

    # Run command
    args.func(args)


if __name__ == "__main__":
    main()
