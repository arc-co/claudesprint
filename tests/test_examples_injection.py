"""Tests for Gold Standard Examples Injection feature."""

from __future__ import annotations

from pathlib import Path

import pytest

from claudesprint.services.path_service import PathService
from claudesprint.services.prompt_service import PromptContext, PromptService


class TestExamplesLoadingFromPackage:
    """Tests for loading examples from package default."""

    @pytest.fixture
    def mock_path_service(self, tmp_path: Path) -> PathService:
        """Create a mock PathService."""
        return PathService(project_root=tmp_path)

    def test_examples_section_included_by_default(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that gold_standard_examples section is included when examples_enabled=True."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="run-tests",
            step_goal="Run test suite",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("run-tests")
        assert "<gold_standard_examples>" in content
        assert "</gold_standard_examples>" in content

    def test_examples_contain_routing_failure_for_run_tests(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that run-tests step gets routing_failure example."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="run-tests",
            step_goal="Run test suite",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("run-tests")
        assert 'type="routing_failure"' in content
        assert "FAIL_CODE" in content


class TestProjectLevelOverride:
    """Tests for project-level examples override."""

    @pytest.fixture
    def mock_path_service(self, tmp_path: Path) -> PathService:
        """Create a mock PathService."""
        return PathService(project_root=tmp_path)

    def test_project_examples_override_package(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that project-level _examples.xml.j2 overrides package default."""
        # Create project-level examples
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "_examples.xml.j2").write_text(
            '<example type="custom">Project-level custom example</example>'
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="implement",
            step_goal="Implement feature",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("implement")
        assert "Project-level custom example" in content
        assert '<example type="custom">' in content


class TestStepNameFiltering:
    """Tests for step-name based filtering of examples."""

    @pytest.fixture
    def mock_path_service(self, tmp_path: Path) -> PathService:
        """Create a mock PathService."""
        return PathService(project_root=tmp_path)

    def test_fix_tests_gets_test_wrong_example(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that fix-tests step gets test_wrong example."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="fix-tests",
            step_goal="Fix failing tests",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("fix-tests")
        assert 'type="test_wrong"' in content
        assert "TEST_WRONG" in content

    def test_code_review_gets_code_review_examples(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that code-review step gets code_review examples."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="code-review",
            step_goal="Review code changes",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("code-review")
        assert 'type="code_review_pass"' in content
        assert 'type="code_review_issues"' in content

    def test_implement_gets_implementation_example(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that implement step gets implementation example."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="implement",
            step_goal="Implement the feature",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("implement")
        assert 'type="implementation_complete"' in content

    def test_write_tests_gets_tests_written_example(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that write-tests step gets tests_written example."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="write-tests",
            step_goal="Write tests",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("write-tests")
        assert 'type="tests_written"' in content

    def test_unrelated_step_no_specific_examples(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that steps without specific examples don't get filtered examples."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="select-issue",
            step_goal="Select an issue",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("select-issue")
        # Should have examples section but no step-specific examples
        assert "<gold_standard_examples>" in content
        # select-issue doesn't have specific examples defined
        assert 'type="routing_failure"' not in content
        assert 'type="test_wrong"' not in content


class TestExamplesEnabledToggle:
    """Tests for examples_enabled toggle functionality."""

    @pytest.fixture
    def mock_path_service(self, tmp_path: Path) -> PathService:
        """Create a mock PathService."""
        return PathService(project_root=tmp_path)

    def test_examples_disabled_excludes_section(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that examples_enabled=False excludes gold_standard_examples section."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="run-tests",
            step_goal="Run test suite",
            examples_enabled=False,
        ))

        content = service.get_prompt_content("run-tests")
        assert "<gold_standard_examples>" not in content
        assert "</gold_standard_examples>" not in content

    def test_examples_enabled_default_true(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that examples_enabled defaults to True."""
        ctx = PromptContext()
        assert ctx.examples_enabled is True

    def test_examples_enabled_in_to_dict(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that examples_enabled is included in to_dict()."""
        ctx = PromptContext(examples_enabled=False)
        result = ctx.to_dict()
        assert "examples_enabled" in result
        assert result["examples_enabled"] is False


class TestMissingExamplesFile:
    """Tests for handling missing _examples.xml.j2 file gracefully."""

    @pytest.fixture
    def mock_path_service(self, tmp_path: Path) -> PathService:
        """Create a mock PathService."""
        return PathService(project_root=tmp_path)

    def test_missing_examples_file_doesnt_break_rendering(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that missing _examples.xml.j2 doesn't break template rendering.

        The 'ignore missing' directive in the include should handle this gracefully.
        This test creates a custom project prompt without _examples.xml.j2.
        """
        # Create project-level prompt without _examples.xml.j2
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)

        # Create a minimal base template that includes examples
        (project_prompts / "_base.xml.j2").write_text("""<prompt>
{% if examples_enabled %}
<gold_standard_examples>
{% include '_examples.xml.j2' ignore missing %}
</gold_standard_examples>
{% endif %}
<content>Test content</content>
</prompt>""")

        # Create a prompt that extends base (no _examples.xml.j2 file)
        (project_prompts / "PROMPT_custom.xml.j2").write_text(
            "{% extends '_base.xml.j2' %}"
        )

        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="custom",
            step_goal="Custom step",
            examples_enabled=True,
        ))

        # Should not raise an error
        content = service.get_prompt_content("custom")
        assert "<gold_standard_examples>" in content
        assert "Test content" in content


class TestExamplesContentStructure:
    """Tests for the structure and content of examples."""

    @pytest.fixture
    def mock_path_service(self, tmp_path: Path) -> PathService:
        """Create a mock PathService."""
        return PathService(project_root=tmp_path)

    def test_examples_have_scenario_tag(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that examples have scenario tags."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="run-tests",
            step_goal="Run tests",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("run-tests")
        assert "<scenario>" in content

    def test_examples_have_analysis_tag(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that examples have analysis tags."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="run-tests",
            step_goal="Run tests",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("run-tests")
        assert "<analysis>" in content

    def test_examples_have_routing_signal_tag(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that examples have routing_signal tags."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="run-tests",
            step_goal="Run tests",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("run-tests")
        # Examples should show routing_signal pattern
        assert "<routing_signal>" in content

    def test_examples_description_present(
        self, mock_path_service: PathService, tmp_path: Path
    ) -> None:
        """Test that gold_standard_examples has description."""
        service = PromptService(mock_path_service, project_root=tmp_path)
        service.set_context(PromptContext(
            step_name="implement",
            step_goal="Implement feature",
            examples_enabled=True,
        ))

        content = service.get_prompt_content("implement")
        assert "Follow these patterns for analysis and action" in content
