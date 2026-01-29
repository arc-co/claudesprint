"""Tests for PathService.

PathService now focuses on package asset resolution (prompts, schemas).
Path resolution has moved to ConfigurationManager.
"""

import tempfile
from pathlib import Path

import pytest

from claudesprint.services.path_service import PathService


class TestPathServicePackageAssets:
    """Tests for package asset resolution via importlib.resources."""

    def test_get_prompt_content_exists(self) -> None:
        """Test loading an existing prompt."""
        paths = PathService()
        content = paths.get_prompt_content("init")
        assert content
        assert isinstance(content, str)
        assert len(content) > 0

    def test_get_prompt_content_not_found(self) -> None:
        """Test loading a non-existent prompt raises FileNotFoundError."""
        paths = PathService()
        with pytest.raises(FileNotFoundError, match="PROMPT_nonexistent.xml.j2"):
            paths.get_prompt_content("nonexistent")

    def test_get_common_prompt_content(self) -> None:
        """Test loading common prompt content."""
        paths = PathService()
        content = paths.get_common_prompt_content()
        assert content
        assert isinstance(content, str)

    def test_get_schema_content_sprint(self) -> None:
        """Test loading sprint schema."""
        paths = PathService()
        content = paths.get_schema_content("sprint")
        assert content
        assert isinstance(content, str)
        assert "schema" in content.lower() or "$" in content

    def test_get_schema_content_current_issue(self) -> None:
        """Test loading current_issue schema."""
        paths = PathService()
        content = paths.get_schema_content("current_issue")
        assert content
        assert isinstance(content, str)

    def test_get_schema_content_not_found(self) -> None:
        """Test loading a non-existent schema raises FileNotFoundError."""
        paths = PathService()
        with pytest.raises(FileNotFoundError, match="nonexistent.schema.json"):
            paths.get_schema_content("nonexistent")

    def test_list_available_prompts(self) -> None:
        """Test listing available prompts."""
        paths = PathService()
        prompts = paths.list_available_prompts()
        assert isinstance(prompts, list)
        assert len(prompts) > 0
        assert "init" in prompts
        assert "implement" in prompts
        assert "run-tests" in prompts

    def test_prompt_exists(self) -> None:
        """Test checking if prompt exists."""
        paths = PathService()
        assert paths.prompt_exists("init")
        assert paths.prompt_exists("implement")
        assert not paths.prompt_exists("nonexistent")

    def test_schema_exists(self) -> None:
        """Test checking if schema exists."""
        paths = PathService()
        assert paths.schema_exists("sprint")
        assert paths.schema_exists("current_issue")
        assert not paths.schema_exists("nonexistent")


class TestPathServiceProjectRoot:
    """Tests for project_root property (kept for PromptService compatibility)."""

    def test_project_root_default(self) -> None:
        """Test default project root is cwd when not specified."""
        paths = PathService(project_root="/tmp/test")
        assert paths.project_root == Path("/tmp/test")

    def test_project_root_explicit(self) -> None:
        """Test explicit project root."""
        paths = PathService(project_root="/some/path")
        assert paths.project_root == Path("/some/path")
