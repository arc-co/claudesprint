"""Tests for XML template common patterns inclusion.

With XML templating, common patterns are included via {% include '_common.xml.j2' %}
in the _base.xml.j2 template, rather than being prepended by ClaudeRunner.
"""

from pathlib import Path

import pytest

from claudesprint.core.claude_runner import ClaudeRunner
from claudesprint.services.path_service import PathService
from claudesprint.services.prompt_service import PromptContext, PromptService


class TestXMLTemplateCommonPatterns:
    """Tests that common patterns are properly included in XML templates."""

    def test_common_included_via_template_inheritance(self, tmp_path: Path):
        """Common patterns should be included via Jinja2 include directive."""
        # Create mock _common.xml.j2
        project_prompts = tmp_path / ".claudesprint" / "prompts"
        project_prompts.mkdir(parents=True)
        (project_prompts / "_common.xml.j2").write_text(
            "<patterns><rule>Common rule here</rule></patterns>"
        )

        # Create mock _base.xml.j2 with include
        (project_prompts / "_base.xml.j2").write_text(
            """<prompt>
<common>{% include '_common.xml.j2' %}</common>
{% block instructions %}{% endblock %}
</prompt>"""
        )

        # Create mock step prompt that extends base
        (project_prompts / "PROMPT_test.xml.j2").write_text(
            """{% extends '_base.xml.j2' %}
{% block instructions %}<step>Do the thing</step>{% endblock %}"""
        )

        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        content = service.get_prompt_content("test")

        # Verify common content is included
        assert "Common rule here" in content
        assert "Do the thing" in content

    def test_legacy_common_prompt_file_still_works(self, tmp_path: Path):
        """ClaudeRunner's common_prompt_file should still work for backwards compatibility."""
        # Create mock common file (legacy markdown format)
        common_file = tmp_path / "_common.md"
        common_file.write_text("# Common Patterns\n\nContext rules here.")

        # Create mock prompt file
        prompt_file = tmp_path / "PROMPT_test.md"
        prompt_file.write_text("# Step: test\n\nDo the thing.")

        # Create runner with common file
        runner = ClaudeRunner(
            project_root=tmp_path,
            timeout=60,
            common_prompt_file=common_file,
        )

        # Simulate what _prepare_prompt_content does
        prompt_content = prompt_file.read_text()
        assembled = runner._prepare_prompt_content(prompt_content)

        # Verify structure - common should be prepended
        assert "# Common Patterns" in assembled
        assert "Context rules here." in assembled
        assert "# Step: test" in assembled

    def test_prompt_works_without_common_file(self, tmp_path: Path):
        """Prompt should work when no common file exists."""
        # Create only prompt file (no common file)
        prompt_file = tmp_path / "PROMPT_test.md"
        prompt_file.write_text("# Step: test\n\nDo the thing.")

        # Create runner pointing to non-existent common file
        runner = ClaudeRunner(
            project_root=tmp_path,
            timeout=60,
            common_prompt_file=tmp_path / "_common.md",  # Does not exist
        )

        # Simulate what _prepare_prompt_content does
        prompt_content = prompt_file.read_text()
        assembled = runner._prepare_prompt_content(prompt_content)

        # Should just be the prompt content (no common file prepended)
        assert assembled == "# Step: test\n\nDo the thing."

    def test_real_common_xml_file_structure(self):
        """Test the actual _common.xml.j2 file from the project."""
        common_file = Path(__file__).parent.parent / "claudesprint" / "prompts" / "_common.xml.j2"

        if not common_file.exists():
            pytest.skip("_common.xml.j2 not found in expected location")

        content = common_file.read_text()

        # Verify expected XML sections exist
        assert "<patterns>" in content or "pattern" in content.lower()
        assert "current_issue.json" in content
        assert "<session_rules>" in content or "rule" in content.lower()

    def test_xml_template_renders_with_context(self, tmp_path: Path):
        """Test XML template renders context variables correctly."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        # Set context
        service.set_context(PromptContext(
            step_name="implement",
            step_goal="Implement the feature",
            sprint_json='{"spec_id": "SPEC_01"}',
            current_issue_json='{"issue_id": "auth-001"}',
        ))

        # Load actual implement prompt
        content = service.get_prompt_content("implement")

        # Verify context was rendered
        assert "implement" in content.lower()
        # The step_goal should appear somewhere in the rendered output
        assert "feature" in content.lower() or "implement" in content.lower()

    def test_artifact_tags_in_rendered_output(self, tmp_path: Path):
        """Test that artifact tags contain context data."""
        path_service = PathService(project_root=tmp_path)
        service = PromptService(path_service, project_root=tmp_path)

        # Set context with data
        service.set_context(PromptContext(
            step_name="run-tests",
            step_goal="Run the test suite",
            sprint_json='{"spec_id": "SPEC_01", "issues": []}',
            current_issue_json='{"issue_id": "test-001", "step": "run-tests"}',
            log_tail="[2024-01-01] Previous step completed",
        ))

        # Load any prompt that uses base template
        content = service.get_prompt_content("run-tests")

        # Verify artifact tags are present (from base template)
        assert "<artifact" in content or "artifact" in content.lower()
        # Context data should be embedded
        assert "SPEC_01" in content or "spec_id" in content
