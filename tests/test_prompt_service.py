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
        # New XML context fields
        assert ctx.step_name == ""
        assert ctx.step_goal == ""
        assert ctx.sprint_json == ""
        assert ctx.current_issue_json == ""
        assert ctx.log_tail == ""
        assert ctx.current_failures == ""

    def test_custom_values(self) -> None:
        """Test context with custom values."""
        ctx = PromptContext(
            browser_validation_enabled=False,
            context7_available=True,
            custom_vars={"foo": "bar"},
            step_name="implement",
            step_goal="Implement the feature",
        )
        assert ctx.browser_validation_enabled is False
        assert ctx.context7_available is True
        assert ctx.custom_vars == {"foo": "bar"}
        assert ctx.step_name == "implement"
        assert ctx.step_goal == "Implement the feature"

    def test_to_dict(self) -> None:
        """Test converting context to dictionary."""
        ctx = PromptContext(
            browser_validation_enabled=True,
            context7_available=False,
            custom_vars={"project_name": "test"},
            step_name="run-tests",
            step_goal="Run the test suite",
        )
        result = ctx.to_dict()
        assert result["browser_validation_enabled"] is True
        assert result["context7_available"] is False
        assert result["project_name"] == "test"
        assert result["step_name"] == "run-tests"
        assert result["step_goal"] == "Run the test suite"

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

    def test_xml_context_fields_in_to_dict(self) -> None:
        """Test that XML context fields are included in to_dict."""
        ctx = PromptContext(
            step_name="code-review",
            step_goal="Review code changes",
            sprint_json='{"spec_id": "SPEC_01"}',
            current_issue_json='{"issue_id": "auth-001"}',
            log_tail="[2024-01-01] Started",
            current_failures="Test failed",
        )
        result = ctx.to_dict()
        assert result["step_name"] == "code-review"
        assert result["step_goal"] == "Review code changes"
        assert result["sprint_json"] == '{"spec_id": "SPEC_01"}'
        assert result["current_issue_json"] == '{"issue_id": "auth-001"}'
        assert result["log_tail"] == "[2024-01-01] Started"
        assert result["current_failures"] == "Test failed"


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
        # Create project-level prompt (must be valid Jinja2 for XML)
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_implement.xml.j2").write_text("<prompt>Project Override</prompt>")

        service = PromptService(mock_path_service, project_root=tmp_path)

        source = service.prompt_source("implement")
        assert source == "project"

        content = service.get_prompt_content("implement", render=False)
        assert content == "<prompt>Project Override</prompt>"

    def test_global_overrides_package(
        self, mock_path_service: PathService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that global-level prompts override package defaults."""
        # Create global-level prompt using env var
        global_prompts = tmp_path / "global_config" / "prompts"
        global_prompts.mkdir(parents=True)
        (global_prompts / "PROMPT_implement.xml.j2").write_text("<prompt>Global Override</prompt>")

        monkeypatch.setenv("CLAUDESPRINT_CONFIG_HOME", str(tmp_path / "global_config"))

        service = PromptService(mock_path_service, project_root=tmp_path)

        source = service.prompt_source("implement")
        assert source == "global"

        content = service.get_prompt_content("implement", render=False)
        assert content == "<prompt>Global Override</prompt>"

    def test_project_overrides_global(
        self, mock_path_service: PathService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that project-level prompts take priority over global."""
        # Create global-level prompt
        global_prompts = tmp_path / "global_config" / "prompts"
        global_prompts.mkdir(parents=True)
        (global_prompts / "PROMPT_implement.xml.j2").write_text("<prompt>Global Override</prompt>")

        monkeypatch.setenv("CLAUDESPRINT_CONFIG_HOME", str(tmp_path / "global_config"))

        # Create project-level prompt
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_implement.xml.j2").write_text("<prompt>Project Override</prompt>")

        service = PromptService(mock_path_service, project_root=tmp_path)

        source = service.prompt_source("implement")
        assert source == "project"

        content = service.get_prompt_content("implement", render=False)
        assert content == "<prompt>Project Override</prompt>"

    def test_common_prompt_hierarchy(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that _common.xml.j2 follows the same hierarchy."""
        # Create project-level common prompt
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "_common.xml.j2").write_text("<patterns>Project Common</patterns>")

        service = PromptService(mock_path_service, project_root=tmp_path)

        content = service.get_common_prompt_content(render=False)
        assert content == "<patterns>Project Common</patterns>"

    def test_prompt_not_found(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test FileNotFoundError for non-existent prompts."""
        service = PromptService(mock_path_service, project_root=tmp_path)

        with pytest.raises(FileNotFoundError, match="PROMPT_nonexistent.xml.j2"):
            service.get_prompt_content("nonexistent")

        with pytest.raises(FileNotFoundError, match="PROMPT_nonexistent.xml.j2"):
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
        (project_prompts / "PROMPT_custom-step.xml.j2").write_text("<prompt>Custom</prompt>")

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
        (project_prompts / "PROMPT_test.xml.j2").write_text(
            "<prompt>Browser enabled: {{ browser_validation_enabled }}</prompt>"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        # Mock the dependency check to return True
        service.set_context(PromptContext(browser_validation_enabled=True))

        content = service.get_prompt_content("test")
        assert content == "<prompt>Browser enabled: True</prompt>"

    def test_conditional_if(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test {% if %} conditionals."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.xml.j2").write_text(
            "{% if browser_validation_enabled %}<available>Browser available</available>{% endif %}"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(browser_validation_enabled=True))

        content = service.get_prompt_content("test")
        assert content == "<available>Browser available</available>"

    def test_conditional_if_not(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test {% if not %} conditionals."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.xml.j2").write_text(
            "{% if not browser_validation_enabled %}<skip>SKIP</skip>{% endif %}<continue>Continue</continue>"
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
        (project_prompts / "PROMPT_test.xml.j2").write_text(
            "{% if context7_available %}<use>context7</use>{% else %}<use>default</use>{% endif %}"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(context7_available=False))

        content = service.get_prompt_content("test")
        assert content == "<use>default</use>"

    def test_multiline_conditional(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test multiline conditionals are handled properly."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.xml.j2").write_text(
            """<prompt>
{% if not browser_validation_enabled %}
<skip>
    <title>SKIP Section</title>
    <note>This is a multiline skip notice.</note>
    <status>skip</status>
</skip>
{% endif %}
<main>
    <title>Main Content</title>
    <body>Rest of prompt.</body>
</main>
</prompt>"""
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(browser_validation_enabled=False))

        content = service.get_prompt_content("test")
        assert "SKIP Section" in content
        assert "<status>skip</status>" in content
        assert "Main Content" in content

    def test_render_false_returns_raw(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test render=False returns raw template content."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.xml.j2").write_text(
            "<prompt>{{ browser_validation_enabled }}</prompt>"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)

        content = service.get_prompt_content("test", render=False)
        assert content == "<prompt>{{ browser_validation_enabled }}</prompt>"

    def test_invalid_template_raises_error(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test invalid Jinja2 template raises FileNotFoundError."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.xml.j2").write_text(
            "{% if unclosed"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)

        # For XML templates loaded via get_template, invalid templates raise error
        with pytest.raises(FileNotFoundError, match="Template not found or invalid"):
            service.get_prompt_content("test")

    def test_render_with_extra_context(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test render_with_context adds extra variables."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(browser_validation_enabled=True))

        content = service.render_with_context(
            "<data>{{ project_name }} - {{ browser_validation_enabled }}</data>",
            extra_context={"project_name": "MyProject"},
        )
        assert content == "<data>MyProject - True</data>"

    def test_xml_context_fields_render(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that XML context fields render correctly in templates."""
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "PROMPT_test.xml.j2").write_text(
            """<prompt>
<role>{{ step_name }} agent</role>
<goal>{{ step_goal }}</goal>
{% if sprint_json %}<sprint>{{ sprint_json }}</sprint>{% endif %}
{% if current_failures %}<failures>{{ current_failures }}</failures>{% endif %}
</prompt>"""
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="implement",
            step_goal="Implement the feature",
            sprint_json='{"spec_id": "SPEC_01"}',
            current_failures="",
        ))

        content = service.get_prompt_content("test")
        assert "<role>implement agent</role>" in content
        assert "<goal>Implement the feature</goal>" in content
        assert '<sprint>{"spec_id": "SPEC_01"}</sprint>' in content
        assert "<failures>" not in content  # Empty, so not rendered


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


class TestStateManagementEnforcement:
    """Tests for state management enforcement (Issue 3)."""

    def test_no_atomic_write_pattern(self, tmp_path: Path) -> None:
        """Ensure atomic_write pattern is removed."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_common_prompt_content(render=False)
        assert "atomic_write" not in content
        assert "cat > .claudesprint/project/current_issue.json.tmp" not in content

    def test_state_management_section_exists(self, tmp_path: Path) -> None:
        """Ensure state_management section exists."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_common_prompt_content(render=False)
        assert "<state_management>" in content
        assert "claudesprint-tools issue step" in content
        assert "claudesprint-tools issue change" in content
        assert "claudesprint-tools issue update" in content
        assert "claudesprint-tools issue failure" in content

    def test_forbidden_actions_documented(self, tmp_path: Path) -> None:
        """Ensure forbidden actions are documented."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_common_prompt_content(render=False)
        assert "<forbidden>" in content
        assert "cat > .claudesprint/" in content
        assert "jq" in content

    def test_update_current_issue_references_cli(self, tmp_path: Path) -> None:
        """Ensure update_current_issue pattern references CLI."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_common_prompt_content(render=False)
        # The update_current_issue pattern should reference CLI
        assert "Use CLI tools for state updates" in content
        assert "claudesprint-tools CLI for schema validation" in content


class TestAnalysisProtocol:
    """Tests for analysis protocol enforcement (Issue 4)."""

    def test_protocol_section_in_base(self, tmp_path: Path) -> None:
        """Ensure protocol section in base template."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        # Read the base template directly
        from importlib.resources import files

        base_content = (
            files("claudesprint.prompts").joinpath("_base.xml.j2").read_text()
        )
        assert '<protocol name="analysis_first">' in base_content
        assert "<analysis>" in base_content
        assert "Analysis MUST appear BEFORE any tool calls" in base_content

    def test_implement_has_analyze_first(self, tmp_path: Path) -> None:
        """Ensure implement prompt requires analysis."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_prompt_content("implement", render=False)
        assert 'name="analyze_first"' in content
        assert "BEFORE any implementation" in content
        assert "Do NOT write any code until analysis is complete" in content

    def test_fix_tests_has_analysis_format(self, tmp_path: Path) -> None:
        """Ensure fix-tests prompt has explicit analysis format."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_prompt_content("fix-tests", render=False)
        assert "Verdict: [TEST_WRONG | CODE_WRONG]" in content
        assert "Do NOT make changes until analysis is output" in content

    def test_run_tests_has_analyze_results(self, tmp_path: Path) -> None:
        """Ensure run-tests prompt has analyze_results phase."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_prompt_content("run-tests", render=False)
        assert 'name="analyze_results"' in content
        assert "CRITICAL: Output analysis BEFORE updating state" in content

    def test_code_review_has_analyze_changes(self, tmp_path: Path) -> None:
        """Ensure code-review prompt has analyze_changes phase."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_prompt_content("code-review", render=False)
        assert 'name="analyze_changes"' in content
        assert "CRITICAL: Output analysis BEFORE making any decisions" in content

    def test_base_cli_constraint_strengthened(self, tmp_path: Path) -> None:
        """Ensure base template has strengthened CLI constraint."""
        from importlib.resources import files

        base_content = (
            files("claudesprint.prompts").joinpath("_base.xml.j2").read_text()
        )
        assert "Use claudesprint-tools CLI for ALL state updates" in base_content
        assert "never manually edit JSON" in base_content


class TestCLIStateUpdatesInPrompts:
    """Tests to verify prompts use CLI for state updates."""

    def test_implement_uses_cli_for_state(self, tmp_path: Path) -> None:
        """Ensure implement prompt uses CLI for state updates."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_prompt_content("implement", render=False)
        assert "claudesprint-tools issue change" in content
        assert "claudesprint-tools issue step write-tests" in content

    def test_write_tests_uses_cli_for_state(self, tmp_path: Path) -> None:
        """Ensure write-tests prompt uses CLI for state updates."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_prompt_content("write-tests", render=False)
        assert "claudesprint-tools issue change" in content
        assert "claudesprint-tools issue step run-tests" in content

    def test_fix_code_review_uses_cli_for_state(self, tmp_path: Path) -> None:
        """Ensure fix-code-review-issues prompt uses CLI for state updates."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_prompt_content("fix-code-review-issues", render=False)
        assert "claudesprint-tools issue change" in content
        assert "claudesprint-tools issue step run-tests" in content
        assert "--clear-failures" in content

    def test_select_issue_uses_cli_for_state(self, tmp_path: Path) -> None:
        """Ensure select-issue prompt uses CLI for state updates."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_prompt_content("select-issue", render=False)
        assert "claudesprint-tools sprint start" in content
        assert "claudesprint-tools issue init" in content


class TestPromptServiceIntegration:
    """Integration tests for PromptService with actual package prompts."""

    def test_load_package_prompt(self, tmp_path: Path) -> None:
        """Test loading an actual package prompt."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        # This should work if the package has an "implement" prompt
        content = service.get_prompt_content("implement", render=False)
        assert len(content) > 0
        # XML templates use extends and have prompt tags
        assert "{% extends" in content or "<prompt" in content

    def test_browser_validation_prompt_with_context(self, tmp_path: Path) -> None:
        """Test browser-validation prompt renders conditionally."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        # Force browser_validation_enabled to False
        service.set_context(PromptContext(browser_validation_enabled=False))

        content = service.get_prompt_content("browser-validation")
        # Should contain the skip section
        assert "skip" in content.lower()
        assert "agent-browser" in content.lower()

    def test_browser_validation_prompt_enabled(self, tmp_path: Path) -> None:
        """Test browser-validation prompt when enabled."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        # Force browser_validation_enabled to True
        service.set_context(PromptContext(browser_validation_enabled=True))

        content = service.get_prompt_content("browser-validation")
        # Should contain the main browser validation instructions
        assert "prerequisites" in content.lower() or "validate" in content.lower()

    def test_template_inheritance(self, tmp_path: Path) -> None:
        """Test that XML templates properly inherit from _base.xml.j2."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        # Set context with XML fields
        service.set_context(PromptContext(
            step_name="implement",
            step_goal="Implement the feature",
        ))

        content = service.get_prompt_content("implement")
        # Should have rendered role from base template
        assert "implement" in content.lower()
        # Should have constraint rules from base template
        assert "rule" in content.lower() or "constraint" in content.lower()
