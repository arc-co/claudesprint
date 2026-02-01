"""Service for managing spec files.

Provides functionality for listing, validating, creating, and reading
project spec files used to initialize sprints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, PackageLoader, TemplateNotFound


@dataclass
class SpecValidationResult:
    """Result of spec file validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    title: str | None = None
    sections_found: list[str] = field(default_factory=list)


@dataclass
class SpecInfo:
    """Information about a spec file."""

    name: str
    path: Path
    title: str | None = None
    description: str | None = None


@dataclass
class SpecTemplate:
    """Information about a spec template."""

    name: str
    display_name: str
    description: str


# Available templates with metadata
SPEC_TEMPLATES: list[SpecTemplate] = [
    SpecTemplate(
        name="web-application",
        display_name="Web Application",
        description="Express/React/SQLite stack with API and frontend",
    ),
    SpecTemplate(
        name="cli-tool",
        display_name="CLI Tool",
        description="Python CLI with Typer framework",
    ),
    SpecTemplate(
        name="api-service",
        display_name="API Service",
        description="FastAPI REST service with database",
    ),
    SpecTemplate(
        name="minimal",
        display_name="Minimal",
        description="Blank template with basic structure only",
    ),
]


class SpecService:
    """Service for managing spec files.

    Handles listing, validation, creation from templates, and reading
    of spec files in the .claudesprint/specs/ directory.
    """

    SPECS_DIR = "specs"
    CLAUDESPRINT_DIR = ".claudesprint"

    def __init__(self, project_root: str | Path) -> None:
        """Initialize the service.

        Args:
            project_root: Path to the project root directory.
        """
        self.project_root = Path(project_root)
        self.claudesprint_dir = self.project_root / self.CLAUDESPRINT_DIR
        self.specs_dir = self.claudesprint_dir / self.SPECS_DIR

    def list_specs(self) -> list[SpecInfo]:
        """List all spec files.

        Looks for .md files in .claudesprint/specs/ and .claudesprint/.

        Returns:
            List of SpecInfo objects for each spec file found.
        """
        specs: list[SpecInfo] = []

        # Check specs directory
        if self.specs_dir.exists():
            for spec_file in sorted(self.specs_dir.glob("*.md")):
                info = self._get_spec_info(spec_file)
                specs.append(info)

        # Also check root .claudesprint directory for .md files
        if self.claudesprint_dir.exists():
            for spec_file in sorted(self.claudesprint_dir.glob("*.md")):
                # Skip README.md and other non-spec files
                if spec_file.name.lower() in ("readme.md",):
                    continue
                info = self._get_spec_info(spec_file)
                specs.append(info)

        return specs

    def get_spec(self, name: str) -> SpecInfo | None:
        """Get a spec by name.

        Args:
            name: Spec name (with or without .md extension).

        Returns:
            SpecInfo if found, None otherwise.
        """
        # Normalize name
        if not name.endswith(".md"):
            name = f"{name}.md"

        # Check specs directory first
        spec_path = self.specs_dir / name
        if spec_path.exists():
            return self._get_spec_info(spec_path)

        # Check root .claudesprint directory
        spec_path = self.claudesprint_dir / name
        if spec_path.exists():
            return self._get_spec_info(spec_path)

        return None

    def read_spec(self, name: str) -> str | None:
        """Read spec file content.

        Args:
            name: Spec name (with or without .md extension).

        Returns:
            File content as string, or None if not found.
        """
        spec = self.get_spec(name)
        if spec is None:
            return None
        return spec.path.read_text()

    def validate_spec(self, name: str) -> SpecValidationResult:
        """Validate a spec file.

        Checks for required sections and structure.

        Args:
            name: Spec name (with or without .md extension).

        Returns:
            SpecValidationResult with validation status and details.
        """
        content = self.read_spec(name)

        if content is None:
            return SpecValidationResult(
                valid=False,
                errors=[f"Spec file '{name}' not found"],
            )

        return self._validate_content(content)

    def validate_content(self, content: str) -> SpecValidationResult:
        """Validate spec content directly.

        Args:
            content: Spec file content.

        Returns:
            SpecValidationResult with validation status and details.
        """
        return self._validate_content(content)

    def _validate_content(self, content: str) -> SpecValidationResult:
        """Internal validation of spec content.

        Args:
            content: Spec file content.

        Returns:
            SpecValidationResult with validation status.
        """
        result = SpecValidationResult(valid=True)

        # Check for title (# heading at start)
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            result.title = title_match.group(1).strip()
        else:
            result.warnings.append("No title heading (# Title) found")

        # Check for sections (## headings)
        sections = re.findall(r"^##\s+(.+)$", content, re.MULTILINE)
        result.sections_found = sections

        if not sections:
            result.warnings.append("No sections (## Section) found")

        # Check for minimum content
        if len(content.strip()) < 50:
            result.errors.append("Spec content is too short (< 50 characters)")
            result.valid = False

        # Check for recommended sections
        found_sections_lower = {s.lower() for s in sections}

        has_issues = any(
            keyword in found_sections_lower
            for keyword in ("issues", "tasks", "user stories", "features", "requirements")
        )

        if not has_issues:
            result.warnings.append(
                "Consider adding an 'Issues' or 'Features' section with specific tasks"
            )

        return result

    def create_spec(
        self,
        name: str,
        template: str,
        project_name: str,
        description: str = "",
    ) -> Path:
        """Create a spec file from a template.

        Args:
            name: Name for the spec file (without .md extension).
            template: Template name (e.g., "web-application", "cli-tool").
            project_name: Name of the project.
            description: Brief description of the project.

        Returns:
            Path to the created spec file.

        Raises:
            ValueError: If template is not found.
            OSError: If directory creation or file writing fails.
        """
        # Ensure specs directory exists
        self.specs_dir.mkdir(parents=True, exist_ok=True)

        # Load and render template
        try:
            env = Environment(
                loader=PackageLoader("claudesprint", "templates/specs"),
                autoescape=False,
                keep_trailing_newline=True,
            )
            template_obj = env.get_template(f"{template}.md.j2")
        except TemplateNotFound:
            raise ValueError(f"Template '{template}' not found") from None

        content = template_obj.render(
            project_name=project_name,
            description=description,
        )

        # Write spec file
        spec_name = self._normalize_name(name)
        spec_path = self.specs_dir / f"{spec_name}.md"
        spec_path.write_text(content)

        return spec_path

    def get_templates(self) -> list[SpecTemplate]:
        """Get list of available spec templates.

        Returns:
            List of SpecTemplate objects.
        """
        return SPEC_TEMPLATES.copy()

    def _get_spec_info(self, path: Path) -> SpecInfo:
        """Extract spec info from a file.

        Args:
            path: Path to the spec file.

        Returns:
            SpecInfo with extracted metadata.
        """
        name = path.stem
        title = None
        description = None

        try:
            content = path.read_text()

            # Extract title from first # heading
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()

            # Extract description from first paragraph after title
            # Look for text after the title line and before the next heading
            desc_match = re.search(
                r"^#\s+.+\n\n(.+?)(?:\n\n|\n#|\Z)",
                content,
                re.MULTILINE | re.DOTALL,
            )
            if desc_match:
                description = desc_match.group(1).strip()
                # Limit to first sentence or 100 chars
                if len(description) > 100:
                    description = description[:97] + "..."

        except (OSError, UnicodeDecodeError):
            pass

        return SpecInfo(
            name=name,
            path=path,
            title=title,
            description=description,
        )

    def _normalize_name(self, name: str) -> str:
        """Normalize a spec name for use as filename.

        Converts to lowercase, replaces spaces with hyphens,
        removes special characters.

        Args:
            name: Raw name input.

        Returns:
            Normalized name safe for use as filename.
        """
        # Lowercase and replace spaces with hyphens
        name = name.lower().strip()
        name = re.sub(r"\s+", "-", name)
        # Remove special characters except hyphens and underscores
        name = re.sub(r"[^a-z0-9\-_]", "", name)
        # Collapse multiple hyphens
        name = re.sub(r"-+", "-", name)
        # Remove leading/trailing hyphens
        name = name.strip("-")

        return name or "spec"
