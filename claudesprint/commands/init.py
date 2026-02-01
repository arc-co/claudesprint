"""Init commands: init (project), plan."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from claudesprint.commands._shared import (
    console,
    get_project_root,
    get_config,
    ConsoleThrobber,
    success,
    error,
    warning,
    running,
    subprocess_line,
    muted,
)


def init_project(
    spec: Annotated[
        Optional[str],
        typer.Option("--spec", "-s", help="Spec file to create sprint from"),
    ] = None,
    goal: Annotated[
        Optional[str],
        typer.Option("--goal", "-g", help="Quick goal description (creates minimal spec automatically)"),
    ] = None,
    description: Annotated[
        Optional[str],
        typer.Option("--description", "-d", help="Sprint description"),
    ] = None,
    debug_conversations: Annotated[
        bool,
        typer.Option(
            "--debug-conversations",
            help="Log raw agent inputs/outputs to agent_conversations.log",
        ),
    ] = False,
) -> None:
    """Initialize a new sprint from a spec file.

    Creates a new sprint.json in .claudesprint/sprints/<spec_id>/ and invokes
    the init agent to populate it with issues from the spec.

    Use --spec to provide an existing spec file, or --goal for quick inline specs.
    """
    # Lazy imports for faster startup
    from claudesprint.core.claude_runner import ClaudeRunner
    from claudesprint.services.configuration_manager import ConfigurationManager
    from claudesprint.services.models_service import ModelsService
    from claudesprint.services.path_service import PathService
    from claudesprint.services.prompt_service import PromptService
    from claudesprint.services.sprint_service import SprintService

    project_root = get_project_root()
    config = get_config()

    # Validate that either --spec or --goal is provided
    if spec is None and goal is None:
        console.print(error("Either --spec or --goal is required"))
        console.print("")
        console.print("Usage:")
        console.print(f"  claudesprint init --spec <spec_file>")
        console.print(f"  claudesprint init --goal \"Build a TODO app with Express\"")
        raise typer.Exit(1)

    # Handle --goal option: create a minimal spec automatically
    if goal is not None:
        from claudesprint.services.spec_service import SpecService

        spec_service = SpecService(project_root)

        # Generate a spec name from the goal
        import re
        goal_slug = re.sub(r"[^a-z0-9]+", "-", goal.lower())[:30].strip("-")
        spec_name = f"goal-{goal_slug}" if goal_slug else "goal-spec"

        # Create minimal spec content
        spec_content = f"""# {goal}

## Overview

{goal}

## Issues

### Issue 1: Implement the Goal

{goal}

**Acceptance Criteria:**
- The implementation meets the stated goal
- Code is functional and tested
"""

        # Ensure specs directory exists
        spec_service.specs_dir.mkdir(parents=True, exist_ok=True)

        # Write the spec
        spec_path = spec_service.specs_dir / f"{spec_name}.md"
        spec_path.write_text(spec_content)

        console.print(success(f"Created quick spec: {spec_path.relative_to(project_root)}"))
        console.print("")
    else:
        # Find spec file (original behavior)
        spec_path = Path(spec)
        if not spec_path.exists():
            # Try looking in .claudesprint/specs/
            spec_path = Path(config.specs_dir) / spec
            if not spec_path.exists():
                # Try adding .md extension
                spec_path = Path(config.specs_dir) / f"{spec}.md"

        if not spec_path.exists():
            console.print(error(f"Spec file not found: {spec}"))
            console.print("Looked in:")
            console.print(f"  • {spec}")
            console.print(f"  • .claudesprint/specs/{spec}")
            console.print(f"  • .claudesprint/specs/{spec}.md")
            raise typer.Exit(1)

    sprint_service = SprintService(config.sprints_dir)
    # Convert to relative path for storage
    try:
        relative_spec_path = spec_path.relative_to(project_root)
    except ValueError:
        # If spec_path is not under project_root, use as-is
        relative_spec_path = spec_path
    sprint_path, sprint = sprint_service.create_sprint_from_spec(
        relative_spec_path, description or ""
    )

    # Ensure sprints directory exists
    sprint_path.parent.mkdir(parents=True, exist_ok=True)

    # Write sprint skeleton
    if not sprint_service.write_sprint(sprint, sprint_path):
        console.print(error("Failed to create sprint"))
        raise typer.Exit(1)

    console.print(success(f"Sprint skeleton created: {sprint_path}"))
    console.print(f"  {muted('Spec ID:')} {sprint.spec_id}")
    console.print(f"  {muted('Spec file:')} {sprint.spec_file}")
    console.print(f"  {muted('Branch:')} {sprint.git_branch}")
    console.print("")

    # Now invoke the init agent to populate the sprint with issues
    # Load prompt from package resources via PromptService
    path_service = PathService(project_root=project_root)
    prompt_service = PromptService(path_service, project_root=project_root)
    try:
        prompt_content = prompt_service.get_prompt_content("init")
    except FileNotFoundError:
        console.print(error("PROMPT_init.xml.j2 not found in package"))
        raise typer.Exit(1)

    # Get model for init step
    cm = ConfigurationManager(project_root)
    models_service = ModelsService.from_config_manager(cm)
    model = models_service.get_model_for_special_step("init")

    # Build context for the agent
    context = f"""## Initialization Context

You are initializing a sprint for:
- **Spec ID**: {sprint.spec_id}
- **Spec file**: {relative_spec_path}
- **Sprint file**: {sprint_path.relative_to(project_root)}

Read the spec file and populate the sprint.json with all required issues.

---"""

    runner = ClaudeRunner(
        project_root,
        config.claude_timeout,
        kill_timeout=config.kill_timeout,
        conversation_log_file=(
            config.conversation_log_file if debug_conversations else None
        ),
    )

    # Start throbber while generating sprint from spec
    throbber = ConsoleThrobber(console)
    throbber.start(f"Generating sprint from spec (model: {model})")
    first_output_received = [False]

    def on_output_with_throbber(line: str) -> None:
        """Handle output, stopping throbber on first line."""
        if not first_output_received[0]:
            first_output_received[0] = True
            throbber.stop()
        console.print(subprocess_line(line))

    result = runner.run_with_content(
        prompt_content,
        source_name="PROMPT_init.xml.j2",
        on_output=on_output_with_throbber,
        model=model,
        context=context,
    )

    # Ensure throbber is stopped even if no output was received
    if throbber.is_running:
        throbber.stop()

    if result.exit_code == 0:
        console.print("")
        console.print(success("Sprint initialization complete."))
        console.print(f"Run 'claudesprint run --spec {sprint.spec_id}' to start the sprint workflow.")
    else:
        console.print(error(f"Init agent failed (exit code: {result.exit_code})"))
        if result.rate_limited:
            console.print(warning("Rate limit detected. Please wait and try again."))
        raise typer.Exit(1)


def run_planner(
    spec: Annotated[
        Optional[str],
        typer.Option("--spec", "-s", help="Spec ID to plan for"),
    ] = None,
    debug_conversations: Annotated[
        bool,
        typer.Option(
            "--debug-conversations",
            help="Log raw agent inputs/outputs to agent_conversations.log",
        ),
    ] = False,
) -> None:
    """Run planning mode to generate issues from a spec file."""
    # Lazy imports for faster startup
    from claudesprint.core.claude_runner import ClaudeRunner
    from claudesprint.services.configuration_manager import ConfigurationManager
    from claudesprint.services.models_service import ModelsService
    from claudesprint.services.path_service import PathService
    from claudesprint.services.prompt_service import PromptService

    project_root = get_project_root()
    config = get_config()

    # Load prompt from package resources via PromptService
    path_service = PathService(project_root=project_root)
    prompt_service = PromptService(path_service, project_root=project_root)
    try:
        prompt_content = prompt_service.get_prompt_content("plan")
    except FileNotFoundError:
        console.print(error("PROMPT_plan.xml.j2 not found in package"))
        raise typer.Exit(1)

    # Get model for plan step
    cm = ConfigurationManager(project_root)
    models_service = ModelsService.from_config_manager(cm)
    model = models_service.get_model_for_special_step("plan")

    console.print(running(f"Running planner (model: {model})..."))

    runner = ClaudeRunner(
        project_root,
        config.claude_timeout,
        kill_timeout=config.kill_timeout,
        conversation_log_file=(
            config.conversation_log_file if debug_conversations else None
        ),
    )
    result = runner.run_with_content(
        prompt_content,
        source_name="PROMPT_plan.xml.j2",
        on_output=lambda line: console.print(subprocess_line(line)),
        model=model,
    )

    if result.exit_code == 0:
        console.print(success("Planning complete."))
    else:
        console.print(error(f"Planning failed (exit code: {result.exit_code})"))
        raise typer.Exit(1)
