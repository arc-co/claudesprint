# Engine Internals

This guide explains how ClaudeSprint works under the hood. Understanding the engine helps with debugging, customization, and contributing.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI Layer                               │
│                       (cli.py, click)                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Workflow Engine                            │
│                      (workflow.py)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Sprint    │  │    Issue    │  │    Step     │              │
│  │    Loop     │──│    Loop     │──│  Executor   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│  State Manager    │ │  Hook Runner      │ │  Notifier         │
│   (state.py)      │ │   (hooks.py)      │ │ (notifications.py)│
└───────────────────┘ └───────────────────┘ └───────────────────┘
            │                   │                   │
            ▼                   ▼                   ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│ current_issue.json│ │   npm/pytest/etc  │ │   Bark/Webhook    │
│   sprint.json     │ │                   │ │                   │
└───────────────────┘ └───────────────────┘ └───────────────────┘
```

## Core Components

### CLI (`cli.py`)

The command-line interface uses Click:

```python
import click
from .services.workflow import WorkflowEngine

@click.group()
def main():
    """ClaudeSprint - Autonomous software development"""
    pass

@main.command()
@click.option('--spec', required=True, help='Specification file')
def init(spec: str):
    """Initialize a sprint from a specification."""
    engine = WorkflowEngine()
    engine.initialize_sprint(spec)

@main.command()
@click.option('-n', '--max-iterations', type=int, default=None)
def run(max_iterations: int):
    """Run the workflow loop."""
    engine = WorkflowEngine()
    engine.run(max_iterations=max_iterations)
```

### Workflow Engine (`workflow.py`)

The core orchestrator:

```python
class WorkflowEngine:
    def __init__(self):
        self.state = StateManager()
        self.hooks = HookRunner()
        self.notifier = Notifier()

    def run(self, max_iterations: int = None):
        """Execute the dual-loop workflow."""
        iteration = 0

        while True:
            # Check exit conditions
            if max_iterations and iteration >= max_iterations:
                self.notifier.send('exit', 'Max iterations reached')
                break

            # Sprint Loop: Check for work
            sprint = self.state.load_sprint()
            if sprint.all_complete():
                self.notifier.send('exit', 'Sprint complete')
                break

            # Issue Loop: Execute current step
            current = self.state.load_current_issue()
            if not current:
                # Select next issue
                current = self._select_next_issue(sprint)

            # Execute step
            result = self._execute_step(current)

            # Handle result
            if result.success:
                self._advance_step(current)
            else:
                self._handle_failure(current, result)

            iteration += 1

    def _execute_step(self, current: CurrentIssue) -> StepResult:
        """Execute a single workflow step."""
        step = current.step
        prompt = self._load_prompt(step)

        # Call Claude API
        response = self._call_claude(prompt, current)

        # Parse and validate response
        return self._parse_response(response)
```

### State Manager (`state.py`)

Handles JSON file operations:

```python
from pathlib import Path
from dataclasses import dataclass
import json

@dataclass
class CurrentIssue:
    schema_version: str
    session_id: str
    timestamp: str
    sprint_path: str
    issue_id: str
    issue_title: str
    step: str
    goal: str
    # ... other fields

class StateManager:
    def __init__(self, project_dir: Path = None):
        self.project_dir = project_dir or Path('.claude/claudesprint/project')
        self.sprints_dir = Path('.claude/claudesprint/sprints')

    def load_current_issue(self) -> Optional[CurrentIssue]:
        """Load current issue state."""
        path = self.project_dir / 'current_issue.json'
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)

        self._validate_schema(data, 'current_issue')
        return CurrentIssue(**data)

    def save_current_issue(self, issue: CurrentIssue) -> None:
        """Save current issue state with backup."""
        path = self.project_dir / 'current_issue.json'
        backup = path.with_suffix('.json.bak')

        # Backup existing
        if path.exists():
            shutil.copy(path, backup)

        # Write new
        with open(path, 'w') as f:
            json.dump(asdict(issue), f, indent=2)

        # Validate
        self._validate_schema(path, 'current_issue')

    def append_log(self, entry: str) -> None:
        """Append to activity log."""
        log_path = self.project_dir / 'current_issue.log'
        timestamp = datetime.now().isoformat()

        with open(log_path, 'a') as f:
            f.write(f"{timestamp} {entry}\n")
```

### Hook Runner (`hooks.py`)

Executes test/build commands:

```python
import subprocess
from dataclasses import dataclass
from typing import List
import json

@dataclass
class HookConfig:
    command: str
    timeout: int = 300
    working_dir: str = None
    env: dict = None
    success_exit_codes: List[int] = None
    failure_patterns: List[str] = None

class HookRunner:
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path('.claude/claudesprint/config/hooks.json')
        self.config = self._load_config()

    def run(self, hook_name: str) -> HookResult:
        """Run a configured hook."""
        if hook_name not in self.config:
            raise ValueError(f"Unknown hook: {hook_name}")

        hook = self.config[hook_name]

        try:
            result = subprocess.run(
                hook.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=hook.timeout,
                cwd=hook.working_dir,
                env={**os.environ, **(hook.env or {})}
            )

            success = result.returncode in (hook.success_exit_codes or [0])

            # Check failure patterns
            if success and hook.failure_patterns:
                for pattern in hook.failure_patterns:
                    if pattern in result.stdout or pattern in result.stderr:
                        success = False
                        break

            return HookResult(
                success=success,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr
            )

        except subprocess.TimeoutExpired:
            return HookResult(
                success=False,
                exit_code=-1,
                error="Timeout exceeded"
            )
```

### Notifier (`notifications.py`)

Sends notifications:

```python
import requests
from pathlib import Path
import json

class Notifier:
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path('.claude/claudesprint/config/notifications.json')
        self.config = self._load_config()

    def send(self, event: str, message: str) -> bool:
        """Send notification for an event."""
        if not self.config.get('enabled', False):
            return False

        # Bark notifications
        if self.config.get('bark', {}).get('enabled', False):
            return self._send_bark(event, message)

        return False

    def _send_bark(self, event: str, message: str) -> bool:
        """Send via Bark push notification."""
        url = self.config['bark']['url']

        titles = {
            'step': 'ClaudeSprint: Step Complete',
            'failure': 'ClaudeSprint: Failure',
            'rate_limit': 'ClaudeSprint: Rate Limited',
            'exit': 'ClaudeSprint: Workflow Exit'
        }

        try:
            response = requests.post(url, json={
                'title': titles.get(event, 'ClaudeSprint'),
                'body': message
            })
            return response.ok
        except Exception:
            return False
```

## Data Models

### Sprint Model

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class IssueStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

class Priority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class HistoryEntry:
    timestamp: str
    action: str
    session_id: str

@dataclass
class Issue:
    id: str
    title: str
    status: IssueStatus
    priority: Priority
    category: str
    acceptance_criteria: List[str]
    dependencies: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    history: List[HistoryEntry] = field(default_factory=list)

@dataclass
class SprintConfig:
    require_testing: bool = True
    require_browser_qa: bool = False

@dataclass
class SprintMetadata:
    total_issues: int
    pending: int
    in_progress: int
    completed: int
    blocked: int

@dataclass
class Sprint:
    schema_version: str
    spec_id: str
    spec_file: str
    description: str
    issues: List[Issue]
    config: SprintConfig
    created_at: str
    last_modified: str
    git_branch: Optional[str] = None
    metadata: Optional[SprintMetadata] = None

    def all_complete(self) -> bool:
        """Check if all issues are complete."""
        return all(i.status == IssueStatus.COMPLETED for i in self.issues)

    def get_available_issues(self) -> List[Issue]:
        """Get issues that can be worked on."""
        completed_ids = {i.id for i in self.issues if i.status == IssueStatus.COMPLETED}

        return [
            issue for issue in self.issues
            if issue.status == IssueStatus.PENDING
            and all(dep in completed_ids for dep in issue.dependencies)
        ]
```

## Step Execution Flow

### Step Lifecycle

```
1. Load current_issue.json
         │
         ▼
2. Validate state
         │
         ▼
3. Load prompt for step
         │
         ▼
4. Inject context (issue, sprint, log)
         │
         ▼
5. Call Claude API
         │
         ▼
6. Parse response
         │
         ▼
7. Validate output
         │
         ▼
8. Update state files
         │
         ▼
9. Append to log
         │
         ▼
10. Return to workflow engine
```

### Prompt Loading

```python
def _load_prompt(self, step: str) -> str:
    """Load and prepare prompt for a step."""
    prompt_path = Path(f'.claude/claudesprint/prompts/PROMPT_{step}.md')

    if not prompt_path.exists():
        raise ValueError(f"No prompt for step: {step}")

    with open(prompt_path) as f:
        return f.read()

def _prepare_context(self, prompt: str, current: CurrentIssue) -> str:
    """Inject context into prompt."""
    # Load additional context
    sprint = self.state.load_sprint()
    log_entries = self._get_recent_log(20)

    # Build full context
    context = {
        'current_issue': asdict(current),
        'sprint': asdict(sprint),
        'recent_log': log_entries
    }

    return f"""
{prompt}

## Current Context
```json
{json.dumps(context, indent=2)}
```
"""
```

## Error Handling

### Retry Logic

```python
def _handle_failure(self, current: CurrentIssue, result: StepResult):
    """Handle step failure."""
    current.retry_count += 1
    current.current_failures = result.error

    if current.retry_count >= self.max_retries:
        self.notifier.send('failure', f"Max retries on {current.step}")
        raise MaxRetryError(current.step, current.current_failures)

    # Determine routing
    if current.step == 'run-tests':
        current.step = 'fix-tests'
    elif current.step == 'code-review':
        current.step = 'fix-code-review-issues'
    # else: retry same step

    self.state.save_current_issue(current)
```

### Recovery

```python
def recover_from_crash(self):
    """Attempt to recover from a crashed session."""
    backup_path = self.project_dir / 'current_issue.json.bak'
    current_path = self.project_dir / 'current_issue.json'

    if not current_path.exists() and backup_path.exists():
        # Restore from backup
        shutil.copy(backup_path, current_path)
        logger.info("Restored from backup")

    # Validate restored state
    try:
        current = self.state.load_current_issue()
        self.state._validate_schema(current, 'current_issue')
    except ValidationError:
        # Backup is also corrupt, reset
        logger.warning("Backup corrupt, resetting state")
        self.reset()
```

## Configuration Loading

```python
class ConfigLoader:
    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path('.claude/claudesprint/config')

    def load_hooks(self) -> Dict[str, HookConfig]:
        return self._load_json('hooks.json')

    def load_models(self) -> Dict[str, str]:
        return self._load_json('models.json')

    def load_notifications(self) -> Dict:
        return self._load_json('notifications.json')

    def load_project(self) -> Dict:
        return self._load_json('project.json')

    def _load_json(self, filename: str) -> Dict:
        path = self.config_dir / filename
        if not path.exists():
            return {}
        with open(path) as f:
            return json.load(f)
```

## Testing the Engine

### Unit Tests

```python
import pytest
from claudesprint.services.state import StateManager
from claudesprint.models import CurrentIssue

def test_state_manager_load():
    manager = StateManager(project_dir=Path('/tmp/test'))

    # Create test state
    test_state = {
        "schema_version": "2.0",
        "session_id": "test",
        # ... other fields
    }

    path = Path('/tmp/test/current_issue.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(test_state))

    # Load and verify
    current = manager.load_current_issue()
    assert current.schema_version == "2.0"
```

### Integration Tests

```python
def test_workflow_run_single_issue():
    """Test running a single issue through the workflow."""
    # Setup
    setup_test_project()

    # Run
    engine = WorkflowEngine()
    engine.run(max_iterations=20)

    # Verify
    sprint = engine.state.load_sprint()
    assert sprint.issues[0].status == IssueStatus.COMPLETED
```

## Performance Considerations

### State File Caching

For frequent reads, consider caching:

```python
class CachingStateManager(StateManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sprint_cache = None
        self._sprint_mtime = None

    def load_sprint(self) -> Sprint:
        path = self._get_sprint_path()
        mtime = path.stat().st_mtime

        if self._sprint_cache and self._sprint_mtime == mtime:
            return self._sprint_cache

        self._sprint_cache = super().load_sprint()
        self._sprint_mtime = mtime
        return self._sprint_cache
```

### Log Rotation

Prevent unbounded log growth:

```python
def rotate_log(self, max_size: int = 1024 * 1024):
    """Rotate log if too large."""
    log_path = self.project_dir / 'current_issue.log'

    if log_path.exists() and log_path.stat().st_size > max_size:
        # Keep last 1000 lines
        lines = log_path.read_text().splitlines()[-1000:]
        log_path.write_text('\n'.join(lines) + '\n')
```

## Next Steps

- [Contributing](./contributing.md): Contribute to the engine
- [Prompt Engineering](./prompt-engineering.md): Customize agent behavior
- [Architecture](../concepts/architecture.md): High-level system design
