"""Tests for InitRepoService."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from claudesprint.services.constants import (
    AGENT_BROWSER_SKILL_CONTENT,
    CLAUDESPRINT_SKILL_CONTENT,
    PROMPTS_README_CONTENT,
)
from claudesprint.services.init_repo_service import (
    InitRepoResult,
    InitRepoService,
)
from claudesprint.services.project_config_service import DEFAULT_PROJECT_CONFIG_TOML


class TestInitRepoServiceExists:
    """Tests for checking if .claudesprint/ exists."""

    def test_exists_returns_false_when_not_initialized(self) -> None:
        """Test exists() returns False when directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            assert service.exists() is False

    def test_exists_returns_true_when_initialized(self) -> None:
        """Test exists() returns True when directory exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".claudesprint").mkdir()
            service = InitRepoService(tmpdir)
            assert service.exists() is True


class TestInitRepoServiceInit:
    """Tests for initializing .claudesprint/ directory."""

    def test_creates_expected_directory_structure(self) -> None:
        """Test init creates state/ and prompts/ directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            assert (Path(tmpdir) / ".claudesprint" / "state").is_dir()
            assert (Path(tmpdir) / ".claudesprint" / "prompts").is_dir()

    def test_creates_prompts_readme(self) -> None:
        """Test init creates prompts/README.md with correct content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            readme_path = Path(tmpdir) / ".claudesprint" / "prompts" / "README.md"
            assert readme_path.exists()
            assert readme_path.read_text() == PROMPTS_README_CONTENT

    def test_result_lists_created_items(self) -> None:
        """Test init result lists created directories and files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            assert ".claudesprint/state/" in result.created_dirs
            assert ".claudesprint/prompts/" in result.created_dirs
            assert ".claudesprint/prompts/README.md" in result.created_files
            assert ".claudesprint/config.toml" in result.created_files


class TestInitRepoServiceConfigToml:
    """Tests for config.toml creation."""

    def test_creates_config_toml(self) -> None:
        """Test init creates config.toml with default content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            config_path = Path(tmpdir) / ".claudesprint" / "config.toml"
            assert config_path.exists()
            assert config_path.read_text() == DEFAULT_PROJECT_CONFIG_TOML

    def test_config_toml_in_created_files(self) -> None:
        """Test config.toml is listed in created_files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            assert ".claudesprint/config.toml" in result.created_files

    def test_force_overwrites_config_toml(self) -> None:
        """Test --force overwrites config.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial structure with custom config
            config_dir = Path(tmpdir) / ".claudesprint"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "config.toml"
            config_path.write_text("# Custom content")

            # Create required dirs to satisfy exists check
            (config_dir / "state").mkdir()
            (config_dir / "prompts").mkdir()

            service = InitRepoService(tmpdir)
            result = service.init(force=True)

            assert result.success is True
            assert config_path.read_text() == DEFAULT_PROJECT_CONFIG_TOML

    def test_does_not_overwrite_without_force(self) -> None:
        """Test init does not overwrite existing config.toml without force."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial structure with custom config
            config_dir = Path(tmpdir) / ".claudesprint"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "config.toml"
            config_path.write_text("# Custom content")

            service = InitRepoService(tmpdir)
            # This should fail because directory exists
            result = service.init(force=False)

            assert result.success is False
            # Original content preserved
            assert config_path.read_text() == "# Custom content"


class TestInitRepoServiceGitignore:
    """Tests for .gitignore handling."""

    def test_creates_gitignore_if_missing(self) -> None:
        """Test init creates .gitignore if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            gitignore_path = Path(tmpdir) / ".gitignore"
            assert gitignore_path.exists()
            assert ".claudesprint/" in gitignore_path.read_text()
            assert ".gitignore" in result.created_files

    def test_appends_to_existing_gitignore(self) -> None:
        """Test init appends to existing .gitignore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitignore_path = Path(tmpdir) / ".gitignore"
            gitignore_path.write_text("node_modules/\n.env\n")

            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            content = gitignore_path.read_text()
            assert "node_modules/" in content
            assert ".env" in content
            assert ".claudesprint/" in content
            assert ".gitignore (updated)" in result.created_files

    def test_no_duplicate_gitignore_entries(self) -> None:
        """Test init doesn't add duplicate .gitignore entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitignore_path = Path(tmpdir) / ".gitignore"
            gitignore_path.write_text("node_modules/\n.claudesprint/\n")

            service = InitRepoService(tmpdir)
            result = service.init(force=True)

            assert result.success is True
            content = gitignore_path.read_text()
            # Count occurrences of .claudesprint/
            assert content.count(".claudesprint/") == 1
            # .gitignore should not be in created files since it wasn't modified
            assert ".gitignore" not in result.created_files
            assert ".gitignore (updated)" not in result.created_files

    def test_handles_gitignore_without_trailing_newline(self) -> None:
        """Test init handles .gitignore without trailing newline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gitignore_path = Path(tmpdir) / ".gitignore"
            gitignore_path.write_text("node_modules/")  # No trailing newline

            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            content = gitignore_path.read_text()
            # Should have proper newlines
            assert content == "node_modules/\n.claudesprint/\n"


class TestInitRepoServiceForce:
    """Tests for --force flag behavior."""

    def test_fails_without_force_if_exists(self) -> None:
        """Test init fails without --force if .claudesprint/ exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".claudesprint").mkdir()

            service = InitRepoService(tmpdir)
            result = service.init(force=False)

            assert result.success is False
            assert "already exists" in result.error
            assert "--force" in result.error

    def test_force_overwrites_readme(self) -> None:
        """Test --force overwrites prompts/README.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial structure with custom README
            prompts_dir = Path(tmpdir) / ".claudesprint" / "prompts"
            prompts_dir.mkdir(parents=True)
            readme_path = prompts_dir / "README.md"
            readme_path.write_text("# Custom content")

            service = InitRepoService(tmpdir)
            result = service.init(force=True)

            assert result.success is True
            assert readme_path.read_text() == PROMPTS_README_CONTENT
            assert ".claudesprint/prompts/README.md" in result.created_files

    def test_force_preserves_state_files(self) -> None:
        """Test --force preserves existing files in state/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial structure with state file
            state_dir = Path(tmpdir) / ".claudesprint" / "state"
            state_dir.mkdir(parents=True)
            state_file = state_dir / "session.json"
            state_file.write_text('{"test": true}')

            # Also create prompts dir to satisfy exists check
            (Path(tmpdir) / ".claudesprint" / "prompts").mkdir()

            service = InitRepoService(tmpdir)
            result = service.init(force=True)

            assert result.success is True
            # State file should be preserved
            assert state_file.exists()
            assert state_file.read_text() == '{"test": true}'


class TestInitRepoServiceGitWarning:
    """Tests for git repository warnings."""

    def test_warns_if_not_git_repo(self) -> None:
        """Test init warns if not in a git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            assert len(result.warnings) == 1
            assert "Not a git repository" in result.warnings[0]

    def test_no_warning_if_git_repo(self) -> None:
        """Test init doesn't warn if in a git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .git directory to simulate git repo
            (Path(tmpdir) / ".git").mkdir()

            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            assert len(result.warnings) == 0


class TestInitRepoServiceOSError:
    """Tests for OSError handling during initialization."""

    def test_handles_permission_error_on_mkdir(self) -> None:
        """Test init handles permission errors when creating directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)

            with patch.object(Path, "mkdir") as mock_mkdir:
                mock_mkdir.side_effect = PermissionError("Permission denied")
                result = service.init()

            assert result.success is False
            assert "Failed to create directory structure" in result.error
            assert "Permission denied" in result.error

    def test_handles_oserror_on_write(self) -> None:
        """Test init handles OSError when writing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)

            with patch.object(Path, "write_text") as mock_write:
                mock_write.side_effect = OSError("Disk full")
                result = service.init()

            assert result.success is False
            assert "Failed to create directory structure" in result.error
            assert "Disk full" in result.error


class TestInitRepoServiceSkill:
    """Tests for Claude Code skill creation."""

    def test_creates_skill_directory_and_file(self) -> None:
        """Test init creates .claude/skills/claudesprint/SKILL.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            skill_path = Path(tmpdir) / ".claude" / "skills" / "claudesprint" / "SKILL.md"
            assert skill_path.exists()
            assert skill_path.read_text() == CLAUDESPRINT_SKILL_CONTENT

    def test_skill_in_created_items(self) -> None:
        """Test skill directory and file are listed in result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            assert ".claude/skills/claudesprint/" in result.created_dirs
            assert ".claude/skills/claudesprint/SKILL.md" in result.created_files

    def test_force_overwrites_skill(self) -> None:
        """Test --force overwrites SKILL.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial structure with custom skill
            skill_dir = Path(tmpdir) / ".claude" / "skills" / "claudesprint"
            skill_dir.mkdir(parents=True)
            skill_path = skill_dir / "SKILL.md"
            skill_path.write_text("# Custom skill content")

            # Also create .claudesprint to satisfy exists check
            (Path(tmpdir) / ".claudesprint").mkdir()

            service = InitRepoService(tmpdir)
            result = service.init(force=True)

            assert result.success is True
            assert skill_path.read_text() == CLAUDESPRINT_SKILL_CONTENT

    def test_preserves_skill_if_exists_without_force(self) -> None:
        """Test init preserves existing SKILL.md when --force is not used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create skill file and .claudesprint to satisfy exists check
            skill_dir = Path(tmpdir) / ".claude" / "skills" / "claudesprint"
            skill_dir.mkdir(parents=True)
            skill_path = skill_dir / "SKILL.md"
            skill_path.write_text("# Custom skill content")
            (Path(tmpdir) / ".claudesprint").mkdir()

            service = InitRepoService(tmpdir)
            # Without force, init fails because .claudesprint exists
            result = service.init(force=False)

            assert result.success is False
            # Skill file should be preserved since init failed
            assert skill_path.read_text() == "# Custom skill content"

    def test_skill_dir_not_listed_if_already_exists(self) -> None:
        """Test skill directory not listed as created if it already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create skill directory first
            skill_dir = Path(tmpdir) / ".claude" / "skills" / "claudesprint"
            skill_dir.mkdir(parents=True)

            service = InitRepoService(tmpdir)
            result = service.init()

            assert result.success is True
            # Directory already existed, so not in created_dirs
            assert ".claude/skills/claudesprint/" not in result.created_dirs
            # But file is still created
            assert ".claude/skills/claudesprint/SKILL.md" in result.created_files

    def test_does_not_overwrite_existing_skill_without_force(self) -> None:
        """Test init does not overwrite existing SKILL.md when force=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create skill file but NOT .claudesprint
            skill_dir = Path(tmpdir) / ".claude" / "skills" / "claudesprint"
            skill_dir.mkdir(parents=True)
            skill_path = skill_dir / "SKILL.md"
            skill_path.write_text("# Custom skill content")

            service = InitRepoService(tmpdir)
            result = service.init(force=False)

            assert result.success is True
            # Skill file should NOT be overwritten
            assert skill_path.read_text() == "# Custom skill content"
            # Skill file should NOT be in created_files (wasn't created)
            assert ".claude/skills/claudesprint/SKILL.md" not in result.created_files


class TestInitRepoResult:
    """Tests for InitRepoResult dataclass."""

    def test_default_values(self) -> None:
        """Test InitRepoResult has expected defaults."""
        result = InitRepoResult(success=True)

        assert result.success is True
        assert result.created_dirs == []
        assert result.created_files == []
        assert result.warnings == []
        assert result.error is None

    def test_with_values(self) -> None:
        """Test InitRepoResult with all values set."""
        result = InitRepoResult(
            success=False,
            created_dirs=["dir1/", "dir2/"],
            created_files=["file1.txt"],
            warnings=["warning1"],
            error="Something went wrong",
        )

        assert result.success is False
        assert result.created_dirs == ["dir1/", "dir2/"]
        assert result.created_files == ["file1.txt"]
        assert result.warnings == ["warning1"]
        assert result.error == "Something went wrong"


class TestInitRepoServiceAgentBrowserSkill:
    """Tests for agent-browser skill creation.

    Note: agent-browser skill is only created when the feature is detected as available.
    These tests explicitly pass detected_features to test conditional skill creation.
    """

    def test_creates_agent_browser_skill_when_feature_available(self) -> None:
        """Test init creates .claude/skills/agent-browser/SKILL.md when feature is available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            # Explicitly enable agent-browser feature
            result = service.init(detected_features={"agent-browser": True, "context7": False})

            assert result.success is True
            skill_path = Path(tmpdir) / ".claude" / "skills" / "agent-browser" / "SKILL.md"
            assert skill_path.exists()
            assert skill_path.read_text() == AGENT_BROWSER_SKILL_CONTENT

    def test_does_not_create_agent_browser_skill_when_feature_unavailable(self) -> None:
        """Test init does not create agent-browser skill when feature is unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            # Explicitly disable agent-browser feature
            result = service.init(detected_features={"agent-browser": False, "context7": False})

            assert result.success is True
            skill_path = Path(tmpdir) / ".claude" / "skills" / "agent-browser" / "SKILL.md"
            assert not skill_path.exists()
            assert ".claude/skills/agent-browser/" not in result.created_dirs
            assert ".claude/skills/agent-browser/SKILL.md" not in result.created_files

    def test_agent_browser_skill_in_created_items_when_available(self) -> None:
        """Test agent-browser skill directory and file are listed in result when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init(detected_features={"agent-browser": True, "context7": False})

            assert result.success is True
            assert ".claude/skills/agent-browser/" in result.created_dirs
            assert ".claude/skills/agent-browser/SKILL.md" in result.created_files

    def test_force_overwrites_agent_browser_skill_when_available(self) -> None:
        """Test --force overwrites agent-browser SKILL.md when feature is available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial structure with custom skill
            skill_dir = Path(tmpdir) / ".claude" / "skills" / "agent-browser"
            skill_dir.mkdir(parents=True)
            skill_path = skill_dir / "SKILL.md"
            skill_path.write_text("# Custom agent-browser skill")

            # Also create .claudesprint to satisfy exists check
            (Path(tmpdir) / ".claudesprint").mkdir()

            service = InitRepoService(tmpdir)
            result = service.init(
                force=True,
                detected_features={"agent-browser": True, "context7": False},
            )

            assert result.success is True
            assert skill_path.read_text() == AGENT_BROWSER_SKILL_CONTENT

    def test_creates_both_skills_when_agent_browser_available(self) -> None:
        """Test init creates both claudesprint and agent-browser skills when feature available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init(detected_features={"agent-browser": True, "context7": False})

            assert result.success is True
            # Both skills should exist
            claudesprint_skill = Path(tmpdir) / ".claude" / "skills" / "claudesprint" / "SKILL.md"
            agent_browser_skill = Path(tmpdir) / ".claude" / "skills" / "agent-browser" / "SKILL.md"
            assert claudesprint_skill.exists()
            assert agent_browser_skill.exists()
            # Both should be in created items
            assert ".claude/skills/claudesprint/" in result.created_dirs
            assert ".claude/skills/agent-browser/" in result.created_dirs
            assert ".claude/skills/claudesprint/SKILL.md" in result.created_files
            assert ".claude/skills/agent-browser/SKILL.md" in result.created_files

    def test_only_claudesprint_skill_when_agent_browser_unavailable(self) -> None:
        """Test init creates only claudesprint skill when agent-browser is unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = InitRepoService(tmpdir)
            result = service.init(detected_features={"agent-browser": False, "context7": False})

            assert result.success is True
            # Only claudesprint skill should exist
            claudesprint_skill = Path(tmpdir) / ".claude" / "skills" / "claudesprint" / "SKILL.md"
            agent_browser_skill = Path(tmpdir) / ".claude" / "skills" / "agent-browser" / "SKILL.md"
            assert claudesprint_skill.exists()
            assert not agent_browser_skill.exists()
            # Only claudesprint should be in created items
            assert ".claude/skills/claudesprint/" in result.created_dirs
            assert ".claude/skills/claudesprint/SKILL.md" in result.created_files
            assert ".claude/skills/agent-browser/" not in result.created_dirs
            assert ".claude/skills/agent-browser/SKILL.md" not in result.created_files
