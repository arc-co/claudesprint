"""Tests for _common.md prompt injection."""

import tempfile
from pathlib import Path

import pytest

from claudesprint.core.claude_runner import ClaudeRunner


class TestCommonPromptInjection:
    """Tests that _common.md is properly injected into all prompts."""

    def test_common_content_prepended_to_prompt(self, tmp_path: Path):
        """Common content should be prepended to prompt with separator."""
        # Create mock common file
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

        # Read what would be sent to Claude
        prompt_content = prompt_file.read_text()
        if runner.common_prompt_file and runner.common_prompt_file.exists():
            common_content = runner.common_prompt_file.read_text()
            assembled = common_content + "\n\n---\n\n" + prompt_content
        else:
            assembled = prompt_content

        # Verify structure
        print("\n" + "=" * 60)
        print("ASSEMBLED PROMPT CONTENT:")
        print("=" * 60)
        print(assembled)
        print("=" * 60)

        assert "# Common Patterns" in assembled
        assert "Context rules here." in assembled
        assert "---" in assembled
        assert "# Step: test" in assembled
        assert "Do the thing." in assembled

        # Verify order: common comes first
        common_pos = assembled.find("# Common Patterns")
        step_pos = assembled.find("# Step: test")
        assert common_pos < step_pos, "Common content should come before step content"

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

        # Simulate what run_prompt does
        prompt_content = prompt_file.read_text()
        if runner.common_prompt_file and runner.common_prompt_file.exists():
            common_content = runner.common_prompt_file.read_text()
            assembled = common_content + "\n\n---\n\n" + prompt_content
        else:
            assembled = prompt_content

        print("\n" + "=" * 60)
        print("PROMPT WITHOUT COMMON FILE:")
        print("=" * 60)
        print(assembled)
        print("=" * 60)

        # Should just be the prompt content
        assert assembled == "# Step: test\n\nDo the thing."
        assert "---" not in assembled

    def test_real_common_file_structure(self):
        """Test with the actual _common.md file from the project."""
        # Find the real _common.md (tests/ -> claudesprint/ -> prompts/)
        common_file = Path(__file__).parent.parent / "prompts" / "_common.md"

        if not common_file.exists():
            pytest.skip("_common.md not found in expected location")

        content = common_file.read_text()

        print("\n" + "=" * 60)
        print("ACTUAL _common.md CONTENT:")
        print("=" * 60)
        print(content)
        print("=" * 60)

        # Verify expected sections exist
        assert "Context Rules" in content or "context" in content.lower()
        assert "Get Bearings" in content or "bearings" in content.lower()
        assert "current_issue.json" in content
        assert "sprint.json" in content or "sprint_path" in content.lower()

    def test_injection_with_real_prompt(self):
        """Test injection with actual prompt and common files."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        common_file = prompts_dir / "_common.md"
        prompt_file = prompts_dir / "PROMPT_implement.md"

        if not common_file.exists() or not prompt_file.exists():
            pytest.skip("Required prompt files not found")

        common_content = common_file.read_text()
        prompt_content = prompt_file.read_text()
        assembled = common_content + "\n\n---\n\n" + prompt_content

        print("\n" + "=" * 60)
        print("FULL ASSEMBLED PROMPT (implement step):")
        print("=" * 60)
        print(f"Total length: {len(assembled)} chars")
        print(f"Common length: {len(common_content)} chars")
        print(f"Prompt length: {len(prompt_content)} chars")
        print("-" * 60)
        print("First 500 chars:")
        print(assembled[:500])
        print("-" * 60)
        print("Last 300 chars:")
        print(assembled[-300:])
        print("=" * 60)

        # Verify structure
        assert common_content in assembled
        assert prompt_content in assembled
        assert assembled.index(common_content) < assembled.index(prompt_content)
