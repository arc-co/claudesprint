"""Hook runner - executes user-configured commands and returns structured results."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claudesprint.services.configuration_manager import ConfigurationManager

logger = logging.getLogger(__name__)


class HookConfigError(Exception):
    """Raised when hook configuration is missing or invalid."""

    pass


@dataclass
class TestFailure:
    """Details about a single test failure."""

    test_name: str
    file_path: str | None = None
    line_number: int | None = None
    error_message: str = ""
    stack_trace: str = ""


@dataclass
class HookResult:
    """Structured result from running a hook."""

    hook_name: str
    passed: bool
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str
    summary: str
    failures: list[TestFailure] = field(default_factory=list)
    timed_out: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "hook_name": self.hook_name,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "summary": self.summary,
            "failures": [
                {
                    "test_name": f.test_name,
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "error_message": f.error_message,
                }
                for f in self.failures
            ],
            "timed_out": self.timed_out,
            "error": self.error,
        }


@dataclass
class HookConfig:
    """Configuration for a hook."""

    command: str
    timeout: int = 300
    working_dir: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    success_exit_codes: list[int] = field(default_factory=lambda: [0])
    failure_patterns: list[str] = field(default_factory=list)
    success_patterns: list[str] = field(default_factory=list)


class HookRunner:
    """Runs configured hooks and parses their output."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        project_root: str | Path | None = None,
        strict: bool = False,
        config_manager: "ConfigurationManager | None" = None,
    ):
        """Initialize the hook runner.

        Args:
            config_path: Path to hooks.json config file.
            project_root: Project root directory for running commands.
            strict: If True, raise HookConfigError on missing/invalid config.
            config_manager: Optional ConfigurationManager for TOML config.
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.config_path = Path(config_path) if config_path else self.project_root / ".claude" / "config" / "hooks.json"
        self._config: dict[str, HookConfig] = {}
        self._config_loaded = False
        self._config_error: str | None = None
        self._config_manager = config_manager
        self._load_config(strict=strict)

    @classmethod
    def from_config_manager(
        cls,
        config_manager: "ConfigurationManager",
        strict: bool = False,
    ) -> "HookRunner":
        """Create a HookRunner that reads from ConfigurationManager.

        Args:
            config_manager: The configuration manager to use.
            strict: If True, raise HookConfigError on invalid config.

        Returns:
            HookRunner instance configured to use TOML config.
        """
        return cls(
            project_root=config_manager.project_root,
            config_manager=config_manager,
            strict=strict,
        )

    def _load_config(self, strict: bool = False) -> None:
        """Load hook configuration from TOML or JSON file.

        Tries TOML config first (via ConfigurationManager), then falls back to JSON.

        Args:
            strict: If True, raise HookConfigError on missing/invalid config.
        """
        # Try ConfigurationManager first
        if self._config_manager is not None:
            if self._load_from_config_manager():
                return

        # Fall back to JSON config
        self._load_from_json(strict=strict)

    def _load_from_config_manager(self) -> bool:
        """Load hook configuration from ConfigurationManager.

        Returns:
            True if config was loaded successfully, False otherwise.
        """
        if self._config_manager is None:
            return False

        if not self._config_manager.exists():
            return False

        try:
            hooks = self._config_manager.project.hooks

            # Convert Pydantic models to HookConfig dataclasses
            # Map hook names to attribute names (validate -> validate_hook due to BaseModel conflict)
            hook_attr_map = {
                "test": "test",
                "lint": "lint",
                "typecheck": "typecheck",
                "build": "build",
                "validate": "validate_hook",
            }
            for hook_name, attr_name in hook_attr_map.items():
                hook_model = getattr(hooks, attr_name, None)
                if hook_model:
                    self._config[hook_name] = HookConfig(
                        command=hook_model.command,
                        timeout=hook_model.timeout,
                        working_dir=None,  # Not in TOML schema
                        env={},  # Not in TOML schema
                        success_exit_codes=list(hook_model.success_exit_codes),
                        failure_patterns=list(hook_model.failure_patterns),
                        success_patterns=list(hook_model.success_patterns),
                    )

            self._config_loaded = True
            return True
        except Exception as e:
            logger.warning(
                "Failed to load hooks from ConfigurationManager: %s. Falling back.",
                e,
            )
            return False

    def _load_from_toml(self) -> bool:
        """Load hook configuration from TOML via ProjectConfigService.

        Returns:
            True if config was loaded successfully, False otherwise.
        """
        if self._project_config_service is None:
            return False

        if not self._project_config_service.exists():
            return False

        try:
            config = self._project_config_service.load()
            hooks = config.hooks

            # Convert Pydantic models to HookConfig dataclasses
            # Map hook names to attribute names (validate -> validate_hook due to BaseModel conflict)
            hook_attr_map = {
                "test": "test",
                "lint": "lint",
                "typecheck": "typecheck",
                "build": "build",
                "validate": "validate_hook",
            }
            for hook_name, attr_name in hook_attr_map.items():
                hook_model = getattr(hooks, attr_name, None)
                if hook_model:
                    self._config[hook_name] = HookConfig(
                        command=hook_model.command,
                        timeout=hook_model.timeout,
                        working_dir=None,  # Not in TOML schema
                        env={},  # Not in TOML schema
                        success_exit_codes=list(hook_model.success_exit_codes),
                        failure_patterns=list(hook_model.failure_patterns),
                        success_patterns=list(hook_model.success_patterns),
                    )

            self._config_loaded = True
            return True
        except Exception as e:
            logger.warning(
                "Failed to load hooks from TOML config: %s. Falling back to JSON.",
                e,
            )
            return False

    def _load_from_json(self, strict: bool = False) -> None:
        """Load hook configuration from JSON file.

        Args:
            strict: If True, raise HookConfigError on missing/invalid config.
        """
        if not self.config_path.exists():
            self._config_error = f"Hook config file not found: {self.config_path}"
            if strict:
                raise HookConfigError(self._config_error)
            return

        try:
            data = json.loads(self.config_path.read_text())
            for name, cfg in data.items():
                if not isinstance(cfg, dict):
                    self._config_error = f"Invalid hook config for '{name}': expected object"
                    if strict:
                        raise HookConfigError(self._config_error)
                    continue

                self._config[name] = HookConfig(
                    command=cfg.get("command", ""),
                    timeout=cfg.get("timeout", 300),
                    working_dir=cfg.get("working_dir"),
                    env=cfg.get("env", {}),
                    success_exit_codes=cfg.get("success_exit_codes", [0]),
                    failure_patterns=cfg.get("failure_patterns", []),
                    success_patterns=cfg.get("success_patterns", []),
                )
            self._config_loaded = True

        except json.JSONDecodeError as e:
            self._config_error = f"Invalid JSON in hook config: {e}"
            if strict:
                raise HookConfigError(self._config_error)

        except KeyError as e:
            self._config_error = f"Missing required key in hook config: {e}"
            if strict:
                raise HookConfigError(self._config_error)

    @property
    def config_loaded(self) -> bool:
        """Whether config was successfully loaded."""
        return self._config_loaded

    @property
    def config_error(self) -> str | None:
        """Error message if config failed to load, None otherwise."""
        return self._config_error

    def get_hook_config(self, hook_name: str) -> HookConfig | None:
        """Get configuration for a specific hook."""
        return self._config.get(hook_name)

    def validate_hook_command(self, hook_name: str) -> tuple[bool, str | None]:
        """Validate that a hook's command can be executed.

        Checks if the first word of the command (the executable) exists.

        Args:
            hook_name: Name of the hook to validate.

        Returns:
            Tuple of (is_valid, error_message if invalid).
        """
        config = self.get_hook_config(hook_name)
        if not config:
            return False, f"Hook '{hook_name}' not configured"

        if not config.command:
            return False, f"Hook '{hook_name}' has empty command"

        # Extract the executable from the command
        cmd_parts = config.command.split()
        if not cmd_parts:
            return False, f"Hook '{hook_name}' has empty command"

        executable = cmd_parts[0]

        # Handle npm/npx specially - check if npm exists
        if executable in ("npm", "npx", "yarn", "pnpm"):
            if not shutil.which(executable):
                return False, f"'{executable}' is not installed or not in PATH"
            return True, None

        # Handle python/pytest specially
        if executable in ("python", "python3", "pytest", "py.test"):
            if not shutil.which(executable):
                return False, f"'{executable}' is not installed or not in PATH"
            return True, None

        # For other commands, check if executable exists
        if not shutil.which(executable):
            # Could be a shell built-in or script, allow it
            return True, None

        return True, None

    def run(self, hook_name: str, capture_output: bool = True) -> HookResult:
        """Run a configured hook and return structured result.

        Args:
            hook_name: Name of the hook (e.g., "test", "lint", "build")
            capture_output: Whether to capture stdout/stderr

        Returns:
            HookResult with pass/fail status and details
        """
        import time

        config = self._config.get(hook_name)
        if not config:
            return HookResult(
                hook_name=hook_name,
                passed=False,
                exit_code=-1,
                duration_seconds=0,
                stdout="",
                stderr="",
                summary=f"Hook '{hook_name}' not configured",
                error=f"No configuration found for hook: {hook_name}",
            )

        if not config.command:
            return HookResult(
                hook_name=hook_name,
                passed=False,
                exit_code=-1,
                duration_seconds=0,
                stdout="",
                stderr="",
                summary=f"Hook '{hook_name}' has no command",
                error="Hook command is empty",
            )

        # Determine working directory
        cwd = Path(config.working_dir) if config.working_dir else self.project_root

        # Merge environment
        env = os.environ.copy()
        env.update(config.env)

        start_time = time.time()
        timed_out = False
        stdout = ""
        stderr = ""
        exit_code = -1

        try:
            result = subprocess.run(
                config.command,
                shell=True,
                cwd=cwd,
                env=env,
                capture_output=capture_output,
                text=True,
                timeout=config.timeout,
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = result.returncode

        except subprocess.TimeoutExpired as e:
            timed_out = True
            stdout = e.stdout or "" if hasattr(e, "stdout") else ""
            stderr = e.stderr or "" if hasattr(e, "stderr") else ""
            exit_code = -1

        except Exception as e:
            return HookResult(
                hook_name=hook_name,
                passed=False,
                exit_code=-1,
                duration_seconds=time.time() - start_time,
                stdout="",
                stderr="",
                summary=f"Hook execution error: {e}",
                error=str(e),
            )

        duration = time.time() - start_time

        # Determine pass/fail
        passed = exit_code in config.success_exit_codes and not timed_out

        # Parse failures from output
        combined_output = stdout + "\n" + stderr
        failures = self._parse_test_failures(combined_output, hook_name)

        # Generate summary
        summary = self._generate_summary(hook_name, passed, exit_code, failures, timed_out, combined_output)

        return HookResult(
            hook_name=hook_name,
            passed=passed,
            exit_code=exit_code,
            duration_seconds=duration,
            stdout=stdout,
            stderr=stderr,
            summary=summary,
            failures=failures,
            timed_out=timed_out,
        )

    def _parse_test_failures(self, output: str, hook_name: str) -> list[TestFailure]:
        """Parse test failures from output.

        Supports common test frameworks: Jest, Vitest, pytest, etc.
        """
        failures = []

        # Jest/Vitest pattern: FAIL src/path/file.test.ts
        fail_file_pattern = r"FAIL\s+(\S+\.(?:test|spec)\.\w+)"
        for match in re.finditer(fail_file_pattern, output):
            failures.append(TestFailure(
                test_name=match.group(1),
                file_path=match.group(1),
            ))

        # Jest assertion pattern: ✕ test name (123 ms)
        test_fail_pattern = r"[✕✗×]\s+(.+?)(?:\s+\(\d+\s*m?s\))?$"
        for match in re.finditer(test_fail_pattern, output, re.MULTILINE):
            test_name = match.group(1).strip()
            if not any(f.test_name == test_name for f in failures):
                failures.append(TestFailure(test_name=test_name))

        # Python pytest pattern: FAILED test_file.py::test_name
        pytest_pattern = r"FAILED\s+(\S+)::(\S+)"
        for match in re.finditer(pytest_pattern, output):
            failures.append(TestFailure(
                test_name=match.group(2),
                file_path=match.group(1),
            ))

        # Extract error messages near failures
        error_pattern = r"(?:Error|AssertionError|TypeError|ReferenceError):\s*(.+?)(?:\n|$)"
        error_matches = list(re.finditer(error_pattern, output))
        for i, failure in enumerate(failures):
            if i < len(error_matches):
                failure.error_message = error_matches[i].group(1).strip()

        return failures

    def _generate_summary(
        self,
        hook_name: str,
        passed: bool,
        exit_code: int,
        failures: list[TestFailure],
        timed_out: bool,
        output: str,
    ) -> str:
        """Generate a human-readable summary."""
        if timed_out:
            return f"{hook_name}: TIMED OUT"

        if passed:
            # Try to extract pass count
            pass_count_pattern = r"(\d+)\s+(?:passed|passing|tests?\s+passed)"
            match = re.search(pass_count_pattern, output, re.IGNORECASE)
            if match:
                return f"{hook_name}: PASSED ({match.group(1)} tests)"
            return f"{hook_name}: PASSED"

        if failures:
            return f"{hook_name}: FAILED ({len(failures)} failures)"

        return f"{hook_name}: FAILED (exit code {exit_code})"


# Module-level convenience functions
_runner: HookRunner | None = None


def _get_runner() -> HookRunner:
    """Get or create the default hook runner."""
    global _runner
    if _runner is None:
        _runner = HookRunner()
    return _runner


def configure_runner(config_path: str | Path | None = None, project_root: str | Path | None = None) -> None:
    """Configure the module-level hook runner."""
    global _runner
    _runner = HookRunner(config_path=config_path, project_root=project_root)


def run_hook(hook_name: str) -> HookResult:
    """Run a configured hook by name."""
    return _get_runner().run(hook_name)


def run_test_hook() -> HookResult:
    """Run the test hook."""
    return run_hook("test")


def run_lint_hook() -> HookResult:
    """Run the lint hook."""
    return run_hook("lint")


def run_build_hook() -> HookResult:
    """Run the build hook."""
    return run_hook("build")


def run_validate_hook() -> HookResult:
    """Run the validate hook (typecheck + lint + test)."""
    return run_hook("validate")
