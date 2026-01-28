"""Tests for PromptService - hierarchical prompt loading and template rendering."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claudesprint.services.path_service import PathService
from claudesprint.services.prompt_service import PromptContext, PromptService


class TestPromptContext:
    """Tests for PromptContext dataclass."""

    def test_default_values(self) -> None:
        """Test default context values."""
        ctx = PromptContext()
        assert ctx.browser_validation_enabled is False
        assert ctx.context7_available is False
        assert ctx.custom_vars == {}

    def test_custom_values(self) -> None:
        """Test context with custom values."""
        ctx = PromptContext(
            browser_validation_enabled=False,
            context7_available=True,
            custom_vars={"foo": "bar"},
        )
        assert ctx.browser_validation_enabled is False
        assert ctx.context7_available is True
        assert ctx.custom_vars == {"foo": "bar"}

    def test_to_dict(self) -> None:
        """Test converting context to dictionary."""
        ctx = PromptContext(
            browser_validation_enabled=True,
            context7_available=False,
            custom_vars={"project_name": "test"},
        )
        result = ctx.to_dict()
        assert result == {
            "browser_validation_enabled": True,
            "context7_available": False,
            "project_name": "test",
        }

    def test_to_dict_custom_vars_override(self) -> None:
        """Test that custom_vars can override default keys."""
        ctx = PromptContext(
            browser_validation_enabled=True,
            custom_vars={"browser_validation_enabled": False},
        )
        result = ctx.to_dict()
        # custom_vars should override the default value
        assert result["browser_validation_enabled"] is False

    def test_to_dict_warns_on_shadowed_keys(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that a warning is logged when custom_vars shadows reserved keys."""
        ctx = PromptContext(
            browser_validation_enabled=True,
            context7_available=False,
            custom_vars={"browser_validation_enabled": False, "context7_available": True},
        )
        with caplog.at_level("WARNING"):
            result = ctx.to_dict()

        # Values should still be overridden
        assert result["browser_validation_enabled"] is False
        assert result["context7_available"] is True

        # Warning should be logged
        assert "custom_vars contains reserved keys" in caplog.text
        assert "browser_validation_enabled" in caplog.text
        assert "context7_available" in caplog.text

    def test_to_dict_no_warning_for_non_reserved_keys(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that no warning is logged for non-reserved custom_vars keys."""
        ctx = PromptContext(
            custom_vars={"my_custom_key": "value", "another_key": 123},
        )
        with caplog.at_level("WARNING"):
            result = ctx.to_dict()

        assert result["my_custom_key"] == "value"
        assert result["another_key"] == 123
        assert "custom_vars contains reserved keys" not in caplog.text


class TestPromptServiceHierarchy:
    """Tests for hierarchical prompt loading."""

    @pytest.fixture
    def mock_path_service(self, tmp_path: Path) -> PathService:
        """Create a mock PathService."""
        return PathService(project_root=tmp_path)

    def test_loads_from_package_by_default(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that prompts load from package when no overrides exist."""
        service = PromptService(mock_path_service, project_root=tmp_path)

        # This should load from package (assuming "implement" exists)
        source = service.prompt_source("implement")
        assert source == "package"

    def test_project_overrides_package(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that project-level prompts override package defaults."""
        # Create project-level prompt
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_implement.md").write_text("# Project Override")

        service = PromptService(mock_path_service, project_root=tmp_path)

        source = service.prompt_source("implement")
        assert source == "project"

        content = service.get_prompt_content("implement", render=False)
        assert content == "# Project Override"

    def test_global_overrides_package(
        self, mock_path_service: PathService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that global-level prompts override package defaults."""
        # Create global-level prompt using env var
        global_prompts = tmp_path / "global_config" / "prompts"
        global_prompts.mkdir(parents=True)
        (global_prompts / "PROMPT_implement.md").write_text("# Global Override")

        monkeypatch.setenv("CLAUDESPRINT_CONFIG_HOME", str(tmp_path / "global_config"))

        service = PromptService(mock_path_service, project_root=tmp_path)

        source = service.prompt_source("implement")
        assert source == "global"

        content = service.get_prompt_content("implement", render=False)
        assert content == "# Global Override"

    def test_project_overrides_global(
        self, mock_path_service: PathService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that project-level prompts take priority over global."""
        # Create global-level prompt
        global_prompts = tmp_path / "global_config" / "prompts"
        global_prompts.mkdir(parents=True)
        (global_prompts / "PROMPT_implement.md").write_text("# Global Override")

        monkeypatch.setenv("CLAUDESPRINT_CONFIG_HOME", str(tmp_path / "global_config"))

        # Create project-level prompt
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_implement.md").write_text("# Project Override")

        service = PromptService(mock_path_service, project_root=tmp_path)

        source = service.prompt_source("implement")
        assert source == "project"

        content = service.get_prompt_content("implement", render=False)
        assert content == "# Project Override"

    def test_common_prompt_hierarchy(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that _common.md follows the same hierarchy."""
        # Create project-level common prompt
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "_common.md").write_text("# Project Common")

        service = PromptService(mock_path_service, project_root=tmp_path)

        content = service.get_common_prompt_content(render=False)
        assert content == "# Project Common"

    def test_prompt_not_found(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test FileNotFoundError for non-existent prompts."""
        service = PromptService(mock_path_service, project_root=tmp_path)

        with pytest.raises(FileNotFoundError, match="PROMPT_nonexistent.md"):
            service.get_prompt_content("nonexistent")

        with pytest.raises(FileNotFoundError, match="PROMPT_nonexistent.md"):
            service.prompt_source("nonexistent")

    def test_prompt_exists(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test prompt_exists method."""
        service = PromptService(mock_path_service, project_root=tmp_path)

        # Package prompt should exist
        assert service.prompt_exists("implement") is True

        # Non-existent prompt
        assert service.prompt_exists("nonexistent") is False

        # Create project-level prompt for custom step
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_custom-step.md").write_text("# Custom")

        assert service.prompt_exists("custom-step") is True


class TestPromptServiceTemplateRendering:
    """Tests for Jinja2 template rendering."""

    @pytest.fixture
    def mock_path_service(self, tmp_path: Path) -> PathService:
        """Create a mock PathService."""
        return PathService(project_root=tmp_path)

    def test_variable_interpolation(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test {{ variable }} interpolation."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.md").write_text(
            "Browser enabled: {{ browser_validation_enabled }}"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        # Mock the dependency check to return True
        service.set_context(PromptContext(browser_validation_enabled=True))

        content = service.get_prompt_content("test")
        assert content == "Browser enabled: True"

    def test_conditional_if(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test {% if %} conditionals."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.md").write_text(
            "{% if browser_validation_enabled %}Browser available{% endif %}"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(browser_validation_enabled=True))

        content = service.get_prompt_content("test")
        assert content == "Browser available"

    def test_conditional_if_not(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test {% if not %} conditionals."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.md").write_text(
            "{% if not browser_validation_enabled %}SKIP{% endif %}Continue"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(browser_validation_enabled=False))

        content = service.get_prompt_content("test")
        assert "SKIP" in content
        assert "Continue" in content

    def test_conditional_else(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test {% if %}...{% else %} conditionals."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.md").write_text(
            "{% if context7_available %}Use context7{% else %}Use default{% endif %}"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(context7_available=False))

        content = service.get_prompt_content("test")
        assert content == "Use default"

    def test_multiline_conditional(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test multiline conditionals are handled properly."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.md").write_text(
            """{% if not browser_validation_enabled %}
## SKIP Section

This is a multiline skip notice.
<status>skip</status>
{% endif %}

## Main Content

Rest of prompt."""
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(browser_validation_enabled=False))

        content = service.get_prompt_content("test")
        assert "## SKIP Section" in content
        assert "<status>skip</status>" in content
        assert "## Main Content" in content

    def test_render_false_returns_raw(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test render=False returns raw template content."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.md").write_text(
            "{{ browser_validation_enabled }}"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)

        content = service.get_prompt_content("test", render=False)
        assert content == "{{ browser_validation_enabled }}"

    def test_invalid_template_returns_raw(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test invalid Jinja2 template returns raw content."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.md").write_text(
            "{% if unclosed"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)

        # Should not raise, should return raw content
        content = service.get_prompt_content("test")
        assert content == "{% if unclosed"

    def test_render_with_extra_context(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test render_with_context adds extra variables."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(browser_validation_enabled=True))

        content = service.render_with_context(
            "{{ project_name }} - {{ browser_validation_enabled }}",
            extra_context={"project_name": "MyProject"},
        )
        assert content == "MyProject - True"


class TestPromptServiceDependencyDetection:
    """Tests for dependency detection (agent-browser, context7)."""

    @pytest.fixture
    def mock_path_service(self, tmp_path: Path) -> PathService:
        """Create a mock PathService."""
        return PathService(project_root=tmp_path)

    @patch("claudesprint.services.prompt_service.subprocess.run")
    @patch("claudesprint.services.prompt_service.shutil.which")
    def test_check_agent_browser_not_installed(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        mock_path_service: PathService,
        tmp_path: Path,
    ) -> None:
        """Test agent-browser detection when not installed."""
        mock_which.return_value = "/usr/bin/npm"
        mock_run.return_value = MagicMock(
            stdout="/usr/lib/node_modules\n└── (empty)",
            returncode=1,
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        result = service._check_agent_browser()
        assert result is False

    @patch("claudesprint.services.prompt_service.subprocess.run")
    @patch("claudesprint.services.prompt_service.shutil.which")
    def test_check_agent_browser_installed(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        mock_path_service: PathService,
        tmp_path: Path,
    ) -> None:
        """Test agent-browser detection when installed."""
        mock_which.return_value = "/usr/bin/npm"
        mock_run.return_value = MagicMock(
            stdout="/usr/lib/node_modules\n└── agent-browser@1.0.0",
            returncode=0,
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        result = service._check_agent_browser()
        assert result is True

    @patch("claudesprint.services.prompt_service.shutil.which")
    def test_check_agent_browser_npm_not_found(
        self,
        mock_which: MagicMock,
        mock_path_service: PathService,
        tmp_path: Path,
    ) -> None:
        """Test agent-browser detection when npm is not installed."""
        mock_which.return_value = None

        service = PromptService(mock_path_service, project_root=tmp_path)
        result = service._check_agent_browser()
        assert result is False

    @patch("claudesprint.services.prompt_service.subprocess.run")
    @patch("claudesprint.services.prompt_service.shutil.which")
    def test_check_agent_browser_timeout(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
        mock_path_service: PathService,
        tmp_path: Path,
    ) -> None:
        """Test agent-browser detection handles timeout."""
        mock_which.return_value = "/usr/bin/npm"
        mock_run.side_effect = subprocess.TimeoutExpired("npm", 5)

        service = PromptService(mock_path_service, project_root=tmp_path)
        result = service._check_agent_browser()
        assert result is False

    @patch("claudesprint.services.prompt_service.shutil.which")
    def test_check_context7_available(
        self,
        mock_which: MagicMock,
        mock_path_service: PathService,
        tmp_path: Path,
    ) -> None:
        """Test context7 detection when available."""
        mock_which.return_value = "/usr/bin/context7"

        service = PromptService(mock_path_service, project_root=tmp_path)
        result = service._check_context7()
        assert result is True
        mock_which.assert_called_with("context7")

    @patch("claudesprint.services.prompt_service.shutil.which")
    def test_check_context7_not_available(
        self,
        mock_which: MagicMock,
        mock_path_service: PathService,
        tmp_path: Path,
    ) -> None:
        """Test context7 detection when not available."""
        mock_which.return_value = None

        service = PromptService(mock_path_service, project_root=tmp_path)
        result = service._check_context7()
        assert result is False

    def test_context_caching(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that context is cached and not re-detected on each access."""
        service = PromptService(mock_path_service, project_root=tmp_path)

        with patch.object(service, "_detect_context") as mock_detect:
            mock_detect.return_value = PromptContext(
                browser_validation_enabled=True,
                context7_available=False,
            )

            # First access should call _detect_context
            _ = service.context
            assert mock_detect.call_count == 1

            # Second access should use cached value
            _ = service.context
            assert mock_detect.call_count == 1

    def test_reload_context(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test reload_context forces re-detection."""
        service = PromptService(mock_path_service, project_root=tmp_path)

        # Prime the cache by accessing context once
        with patch.object(service, "_detect_context") as mock_detect_initial:
            mock_detect_initial.return_value = PromptContext(browser_validation_enabled=True)
            _ = service.context

        with patch.object(service, "_detect_context") as mock_detect:
            mock_detect.return_value = PromptContext(
                browser_validation_enabled=False,
                context7_available=True,
            )

            new_context = service.reload_context()
            assert new_context.browser_validation_enabled is False
            assert new_context.context7_available is True
            mock_detect.assert_called_once()

    def test_set_context(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test set_context explicitly sets the context."""
        service = PromptService(mock_path_service, project_root=tmp_path)

        custom_context = PromptContext(
            browser_validation_enabled=True,
            context7_available=True,
            custom_vars={"test_var": "value"},
        )
        service.set_context(custom_context)

        assert service.context is custom_context
        assert service.context.browser_validation_enabled is True
        assert service.context.context7_available is True
        assert service.context.custom_vars == {"test_var": "value"}


class TestPromptServiceDirectoryPaths:
    """Tests for directory path resolution."""

    @pytest.fixture
    def mock_path_service(self, tmp_path: Path) -> PathService:
        """Create a mock PathService."""
        return PathService(project_root=tmp_path)

    def test_raises_valueerror_when_no_project_root(self) -> None:
        """Test that ValueError is raised when no project root can be determined."""
        # Create a PathService with project_root=None
        mock_path_service = MagicMock(spec=PathService)
        mock_path_service.project_root = None

        with pytest.raises(ValueError, match="project_root must be provided"):
            PromptService(mock_path_service, project_root=None)

    def test_uses_path_service_project_root_when_not_provided(
        self, tmp_path: Path
    ) -> None:
        """Test that path_service.project_root is used when project_root is not provided."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service)  # No project_root argument

        assert service._project_root == tmp_path

    def test_project_prompts_dir(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test project_prompts_dir property."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        expected = tmp_path / ".claudesprint" / "prompts"
        assert service.project_prompts_dir == expected

    def test_global_prompts_dir_env_override(
        self, mock_path_service: PathService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test global_prompts_dir with CLAUDESPRINT_CONFIG_HOME."""
        monkeypatch.setenv("CLAUDESPRINT_CONFIG_HOME", "/custom/config")
        service = PromptService(mock_path_service, project_root=tmp_path)
        assert service.global_prompts_dir == Path("/custom/config/prompts")

    @pytest.mark.skipif(os.name == "nt", reason="XDG_CONFIG_HOME not applicable on Windows")
    def test_global_prompts_dir_xdg_override(
        self, mock_path_service: PathService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test global_prompts_dir with XDG_CONFIG_HOME."""
        monkeypatch.delenv("CLAUDESPRINT_CONFIG_HOME", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg/config")
        service = PromptService(mock_path_service, project_root=tmp_path)
        assert service.global_prompts_dir == Path("/xdg/config/claudesprint/prompts")

    def test_global_prompts_dir_default(
        self, mock_path_service: PathService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test global_prompts_dir default path."""
        monkeypatch.delenv("CLAUDESPRINT_CONFIG_HOME", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        # Skip detailed assertion as it's platform-dependent
        service = PromptService(mock_path_service, project_root=tmp_path)
        # Just ensure it returns a Path object ending in "prompts"
        assert service.global_prompts_dir.name == "prompts"
        assert "claudesprint" in str(service.global_prompts_dir)


class TestPromptServiceIntegration:
    """Integration tests for PromptService with actual package prompts."""

    def test_load_package_prompt(self, tmp_path: Path) -> None:
        """Test loading an actual package prompt."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        # This should work if the package has an "implement" prompt
        content = service.get_prompt_content("implement", render=False)
        assert len(content) > 0
        assert "implement" in content.lower() or "#" in content

    def test_browser_validation_prompt_with_context(self, tmp_path: Path) -> None:
        """Test browser-validation prompt renders conditionally."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        # Force browser_validation_enabled to False
        service.set_context(PromptContext(browser_validation_enabled=False))

        content = service.get_prompt_content("browser-validation")
        # Should contain the SKIP section
        assert "SKIP" in content
        assert "agent-browser" in content.lower()

    def test_browser_validation_prompt_enabled(self, tmp_path: Path) -> None:
        """Test browser-validation prompt when enabled."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        # Force browser_validation_enabled to True
        service.set_context(PromptContext(browser_validation_enabled=True))

        content = service.get_prompt_content("browser-validation")
        # Should NOT start with SKIP section (but may still mention SKIP status)
        assert not content.startswith("# Step: browser-validation\n\n## SKIP")
