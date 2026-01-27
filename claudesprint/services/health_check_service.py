"""Health check service for environment diagnostics.

Implements the `claudesprint doctor` command functionality to verify
the development environment is properly configured.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from importlib.metadata import PackageNotFoundError, distribution, version
from pathlib import Path


class CheckStatus(str, Enum):
    """Status of an individual health check."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    status: CheckStatus
    message: str
    details: str | None = None
    fixable: bool = False
    fix_command: str | None = None

    @property
    def is_ok(self) -> bool:
        """Check if this result is OK."""
        return self.status == CheckStatus.OK

    @property
    def is_error(self) -> bool:
        """Check if this result is an error."""
        return self.status == CheckStatus.ERROR


@dataclass
class HealthReport:
    """Complete health check report."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        """Check if all checks passed (no errors)."""
        return not any(check.is_error for check in self.checks)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(check.status == CheckStatus.WARNING for check in self.checks)

    @property
    def error_count(self) -> int:
        """Count of checks with errors."""
        return sum(1 for check in self.checks if check.is_error)

    @property
    def warning_count(self) -> int:
        """Count of checks with warnings."""
        return sum(1 for check in self.checks if check.status == CheckStatus.WARNING)

    @property
    def fixable_issues(self) -> list[CheckResult]:
        """Get list of issues that can be auto-fixed."""
        return [check for check in self.checks if check.fixable and not check.is_ok]

    def add(self, result: CheckResult) -> None:
        """Add a check result to the report."""
        self.checks.append(result)


# Minimum Python version required
MIN_PYTHON_VERSION = (3, 10)

# Required Python packages
REQUIRED_PACKAGES = [
    "rich",
    "typer",
    "pydantic",
    "httpx",
    "jinja2",
]

# Optional dependencies: (name, type, description)
OPTIONAL_DEPS: list[tuple[str, str, str]] = [
    ("agent-browser", "npm", "Browser automation for E2E testing"),
    ("npm", "system", "Required for agent-browser installation"),
]

# Timeout constants (in seconds)
VERSION_CHECK_TIMEOUT = 10
INSTALL_TIMEOUT = 120


class HealthCheckService:
    """Service for checking environment health.

    Verifies that all required dependencies are installed and configured
    correctly for ClaudeSprint to function.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the service.

        Args:
            project_root: Optional project root path. Defaults to cwd.
        """
        self.project_root = project_root or Path.cwd()

    def run_all_checks(self, verbose: bool = False) -> HealthReport:
        """Run all health checks.

        Args:
            verbose: Include detailed information in results.

        Returns:
            HealthReport with all check results.
        """
        report = HealthReport()

        # Core checks
        report.add(self.check_python_version(verbose))
        report.add(self.check_required_packages(verbose))
        report.add(self.check_claude_cli(verbose))
        report.add(self.check_project_structure(verbose))

        # Optional checks
        for check in self.check_optional_deps(verbose):
            report.add(check)

        return report

    def check_python_version(self, verbose: bool = False) -> CheckResult:
        """Check if Python version meets requirements.

        Args:
            verbose: Include version details.

        Returns:
            CheckResult for Python version.
        """
        current = sys.version_info[:2]
        version_str = f"{current[0]}.{current[1]}"
        required_str = f"{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}"

        if current >= MIN_PYTHON_VERSION:
            return CheckResult(
                name="Python Version",
                status=CheckStatus.OK,
                message=f"Python {version_str}",
                details=sys.version if verbose else None,
            )
        else:
            return CheckResult(
                name="Python Version",
                status=CheckStatus.ERROR,
                message=f"Python {version_str} (requires {required_str}+)",
                details=(
                    f"Current: {sys.version}\nRequired: {required_str} or higher"
                    if verbose
                    else None
                ),
            )

    def check_required_packages(self, verbose: bool = False) -> CheckResult:
        """Check if required Python packages are installed.

        Args:
            verbose: Include package version details.

        Returns:
            CheckResult for required packages.
        """
        missing: list[str] = []
        installed: list[str] = []

        for package in REQUIRED_PACKAGES:
            if self._is_package_installed(package):
                if verbose:
                    pkg_version = self._get_package_version(package)
                    installed.append(f"{package}=={pkg_version}" if pkg_version else package)
            else:
                missing.append(package)

        if not missing:
            return CheckResult(
                name="Required Packages",
                status=CheckStatus.OK,
                message="All required packages installed",
                details="\n".join(installed) if verbose else None,
            )
        else:
            return CheckResult(
                name="Required Packages",
                status=CheckStatus.ERROR,
                message=f"Missing packages: {', '.join(missing)}",
                details=(
                    f"Missing: {', '.join(missing)}\nInstalled: {', '.join(installed)}"
                    if verbose
                    else None
                ),
                fixable=True,
                fix_command=f"pip install {' '.join(missing)}",
            )

    def check_claude_cli(self, verbose: bool = False) -> CheckResult:
        """Check if Claude CLI is installed and accessible.

        Args:
            verbose: Include version details.

        Returns:
            CheckResult for Claude CLI.
        """
        claude_path = shutil.which("claude")

        if not claude_path:
            return CheckResult(
                name="Claude CLI",
                status=CheckStatus.ERROR,
                message="Claude CLI not found in PATH",
                details=(
                    "Install from: https://docs.anthropic.com/en/docs/claude-code"
                    if verbose
                    else None
                ),
            )

        # Try to get version
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=VERSION_CHECK_TIMEOUT,
            )
            version = result.stdout.strip() or result.stderr.strip()
            return CheckResult(
                name="Claude CLI",
                status=CheckStatus.OK,
                message="Claude CLI installed",
                details=f"Path: {claude_path}\nVersion: {version}" if verbose else None,
            )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            return CheckResult(
                name="Claude CLI",
                status=CheckStatus.WARNING,
                message="Claude CLI found but version check failed",
                details=f"Path: {claude_path}" if verbose else None,
            )

    def check_project_structure(self, verbose: bool = False) -> CheckResult:
        """Check if project has ClaudeSprint structure.

        Args:
            verbose: Include directory listing.

        Returns:
            CheckResult for project structure.
        """
        claudesprint_dir = self.project_root / ".claudesprint"

        if not claudesprint_dir.exists():
            return CheckResult(
                name="Project Structure",
                status=CheckStatus.WARNING,
                message="No .claudesprint/ directory found",
                details=(
                    "Run 'claudesprint initrepo' to initialize ClaudeSprint in this project"
                    if verbose
                    else None
                ),
                fixable=True,
                fix_command="claudesprint initrepo",
            )

        # Check for expected subdirectories
        expected_dirs = ["state", "prompts"]
        missing_dirs = [
            d for d in expected_dirs if not (claudesprint_dir / d).exists()
        ]

        if missing_dirs:
            return CheckResult(
                name="Project Structure",
                status=CheckStatus.WARNING,
                message=f"Missing directories: {', '.join(missing_dirs)}",
                details=(
                    f"Expected in .claudesprint/: {', '.join(expected_dirs)}"
                    if verbose
                    else None
                ),
            )

        return CheckResult(
            name="Project Structure",
            status=CheckStatus.OK,
            message=".claudesprint/ directory configured",
            details=(
                f"Found: {', '.join(d.name for d in claudesprint_dir.iterdir() if d.is_dir())}"
                if verbose
                else None
            ),
        )

    def check_optional_deps(self, verbose: bool = False) -> list[CheckResult]:
        """Check optional dependencies.

        Args:
            verbose: Include detailed information.

        Returns:
            List of CheckResults for optional dependencies.
        """
        results: list[CheckResult] = []

        for name, dep_type, description in OPTIONAL_DEPS:
            if dep_type == "npm":
                result = self._check_npm_package(name, description, verbose)
            else:
                result = self._check_system_command(name, description, verbose)
            results.append(result)

        return results

    def _check_npm_package(
        self, name: str, description: str, verbose: bool
    ) -> CheckResult:
        """Check if an npm package is installed globally.

        Args:
            name: Package name.
            description: Description of the package.
            verbose: Include details.

        Returns:
            CheckResult for the package.
        """
        # Check if command exists (most npm packages install a CLI)
        cmd_path = shutil.which(name)

        if cmd_path:
            return CheckResult(
                name=f"{name} (optional)",
                status=CheckStatus.OK,
                message=f"{description}",
                details=f"Path: {cmd_path}" if verbose else None,
            )
        else:
            return CheckResult(
                name=f"{name} (optional)",
                status=CheckStatus.WARNING,
                message=f"Not installed - {description}",
                details=(
                    f"Install with: npm install -g {name}"
                    if verbose
                    else None
                ),
                fixable=True,
                fix_command=f"npm install -g {name}",
            )

    def _check_system_command(
        self, name: str, description: str, verbose: bool
    ) -> CheckResult:
        """Check if a system command is available.

        Args:
            name: Command name.
            description: Description of the command.
            verbose: Include details.

        Returns:
            CheckResult for the command.
        """
        cmd_path = shutil.which(name)

        if cmd_path:
            return CheckResult(
                name=f"{name} (optional)",
                status=CheckStatus.OK,
                message=f"{description}",
                details=f"Path: {cmd_path}" if verbose else None,
            )
        else:
            return CheckResult(
                name=f"{name} (optional)",
                status=CheckStatus.WARNING,
                message=f"Not installed - {description}",
            )

    def _is_package_installed(self, package: str) -> bool:
        """Check if a Python package is installed.

        Args:
            package: Package name.

        Returns:
            True if installed.
        """
        try:
            distribution(package)
            return True
        except PackageNotFoundError:
            return False

    def _get_package_version(self, package: str) -> str | None:
        """Get the version of an installed package.

        Args:
            package: Package name.

        Returns:
            Version string or None.
        """
        try:
            return version(package)
        except PackageNotFoundError:
            return None

    def _run_install_command(
        self,
        cmd: str,
        on_output: Callable[[str], None] | None = None,
    ) -> bool:
        """Run an install command (pip or npm).

        Args:
            cmd: The command to run.
            on_output: Optional callback for command output.

        Returns:
            True if command succeeded.
        """
        try:
            result = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=INSTALL_TIMEOUT,
            )
            if on_output:
                if result.stdout:
                    on_output(result.stdout)
                if result.stderr:
                    on_output(result.stderr)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            return False

    def attempt_fix(
        self,
        check: CheckResult,
        on_output: Callable[[str], None] | None = None,
    ) -> bool:
        """Attempt to fix a fixable issue.

        Args:
            check: The check result with a fix_command.
            on_output: Optional callback for command output.

        Returns:
            True if fix was successful.
        """
        if not check.fixable or not check.fix_command:
            return False

        cmd = check.fix_command

        # Handle pip and npm install commands
        if cmd.startswith("pip install") or cmd.startswith("npm install"):
            return self._run_install_command(cmd, on_output)

        # For claudesprint commands, return False - these should be run manually
        if cmd.startswith("claudesprint "):
            return False

        return False

    def fix_all(
        self,
        report: HealthReport,
        on_output: Callable[[str], None] | None = None,
    ) -> tuple[int, int]:
        """Attempt to fix all fixable issues.

        Args:
            report: Health report with issues to fix.
            on_output: Optional callback for command output.

        Returns:
            Tuple of (successful_fixes, failed_fixes).
        """
        successful = 0
        failed = 0

        for check in report.fixable_issues:
            if self.attempt_fix(check, on_output):
                successful += 1
            else:
                failed += 1

        return successful, failed
