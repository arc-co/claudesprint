"""Tests for ClaudeHookService."""

import io
import sys
from unittest.mock import patch

from claudesprint.services.claude_hook_service import (
    ClaudeHookService,
    HookInput,
    HookResult,
    HookType,
)


class TestHookInput:
    """Tests for HookInput parsing."""

    def test_from_stdin_parses_valid_json(self) -> None:
        """Test parsing valid JSON from stdin."""
        json_input = '{"tool_name": "Bash", "tool_input": {"command": "npm test"}}'
        with patch.object(sys, "stdin", io.StringIO(json_input)):
            hook_input = HookInput.from_stdin()

        assert hook_input.tool_name == "Bash"
        assert hook_input.tool_input == {"command": "npm test"}

    def test_from_stdin_handles_empty_input(self) -> None:
        """Test handling empty stdin."""
        with patch.object(sys, "stdin", io.StringIO("")):
            hook_input = HookInput.from_stdin()

        assert hook_input.tool_name is None
        assert hook_input.tool_input is None

    def test_from_stdin_handles_invalid_json(self) -> None:
        """Test handling invalid JSON."""
        with patch.object(sys, "stdin", io.StringIO("not valid json")):
            hook_input = HookInput.from_stdin()

        assert hook_input.tool_name is None
        assert hook_input.tool_input is None

    def test_from_stdin_handles_partial_data(self) -> None:
        """Test handling JSON without all expected fields."""
        json_input = '{"tool_name": "Bash"}'
        with patch.object(sys, "stdin", io.StringIO(json_input)):
            hook_input = HookInput.from_stdin()

        assert hook_input.tool_name == "Bash"
        assert hook_input.tool_input == {}


class TestServerGuard:
    """Tests for server-guard hook."""

    def test_allows_normal_commands(self) -> None:
        """Test that normal commands are allowed."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": "npm test"})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_blocks_watch_flag(self) -> None:
        """Test blocking commands with --watch flag."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": "npm test --watch"})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.BLOCK

    def test_blocks_watch_word(self) -> None:
        """Test blocking commands with 'watch' keyword."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": "npm run watch"})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.BLOCK

    def test_blocks_interactive_git_rebase(self) -> None:
        """Test blocking git rebase -i."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": "git rebase -i HEAD~3"})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.BLOCK

    def test_blocks_interactive_git_add(self) -> None:
        """Test blocking git add -p."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": "git add -p"})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.BLOCK

    def test_allows_git_commit_with_message(self) -> None:
        """Test allowing git commit with -m flag."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": 'git commit -m "fix: bug"'})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_blocks_git_commit_without_message(self) -> None:
        """Test blocking git commit without -m (opens editor)."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": "git commit"})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.BLOCK

    def test_allows_empty_command(self) -> None:
        """Test allowing empty command."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": ""})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_allows_missing_command(self) -> None:
        """Test allowing when command is missing."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_blocks_tail_follow(self) -> None:
        """Test blocking tail -f commands."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": "tail -f /var/log/syslog"})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.BLOCK


class TestBrowserGuard:
    """Tests for browser-guard hook."""

    def test_allows_by_default(self) -> None:
        """Test that browser-guard allows operations by default."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"skill": "agent-browser"})

        result = service.execute_hook(HookType.BROWSER_GUARD, hook_input)

        assert result == HookResult.ALLOW


class TestAutonomousContinue:
    """Tests for autonomous-continue hook."""

    def test_allows_by_default(self) -> None:
        """Test that autonomous-continue allows stop by default."""
        service = ClaudeHookService()
        hook_input = HookInput()

        result = service.execute_hook(HookType.AUTONOMOUS_CONTINUE, hook_input)

        assert result == HookResult.ALLOW


class TestHelperMethods:
    """Tests for helper methods."""

    def test_is_watch_command(self) -> None:
        """Test is_watch_command detection."""
        service = ClaudeHookService()

        assert service.is_watch_command("npm test --watch") is True
        assert service.is_watch_command("npm run watch") is True
        assert service.is_watch_command("npm test") is False

    def test_is_interactive_git_command(self) -> None:
        """Test is_interactive_git_command detection."""
        service = ClaudeHookService()

        assert service.is_interactive_git_command("git rebase -i main") is True
        assert service.is_interactive_git_command("git add -p") is True
        assert service.is_interactive_git_command("git add file.txt") is False

    def test_is_server_command(self) -> None:
        """Test is_server_command detection."""
        service = ClaudeHookService()

        assert service.is_server_command("npm run dev") is True
        assert service.is_server_command("yarn start") is True
        assert service.is_server_command("npm test") is False


class TestHookTypes:
    """Tests for HookType enum."""

    def test_hook_type_values(self) -> None:
        """Test hook type string values."""
        assert HookType.SERVER_GUARD.value == "server-guard"
        assert HookType.BROWSER_GUARD.value == "browser-guard"
        assert HookType.AUTONOMOUS_CONTINUE.value == "autonomous-continue"


class TestHookResult:
    """Tests for HookResult enum."""

    def test_hook_result_values(self) -> None:
        """Test hook result exit code values."""
        assert HookResult.ALLOW.value == 0
        assert HookResult.BLOCK.value == 2


class TestQuotedContentFalsePositives:
    """Tests to ensure quoted content doesn't trigger false positives."""

    def test_allows_commit_message_with_watch(self) -> None:
        """Test that 'watch' in a commit message is allowed."""
        service = ClaudeHookService()
        hook_input = HookInput(
            tool_input={"command": 'git commit -m "watch out for this bug"'}
        )

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_allows_echo_with_watch(self) -> None:
        """Test that 'watch' in an echo statement is allowed."""
        service = ClaudeHookService()
        hook_input = HookInput(
            tool_input={"command": 'echo "Remember to watch the logs"'}
        )

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_allows_commit_message_with_serve(self) -> None:
        """Test that 'serve' in a commit message is allowed."""
        service = ClaudeHookService()
        hook_input = HookInput(
            tool_input={"command": "git commit -m 'Add serve endpoint'"}
        )

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_allows_grep_for_watch(self) -> None:
        """Test that grepping for 'watch' is allowed."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": 'grep "watch" package.json'})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_still_blocks_actual_watch_command(self) -> None:
        """Test that actual watch commands are still blocked."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": "npm run watch"})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.BLOCK

    def test_still_blocks_watch_with_quoted_args(self) -> None:
        """Test that watch commands with quoted args are still blocked."""
        service = ClaudeHookService()
        hook_input = HookInput(
            tool_input={"command": 'npm run watch --include "src/**/*.ts"'}
        )

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.BLOCK

    def test_helper_ignores_quoted_watch(self) -> None:
        """Test is_watch_command ignores quoted content."""
        service = ClaudeHookService()

        assert service.is_watch_command('git commit -m "watch this"') is False
        assert service.is_watch_command("npm run watch") is True

    def test_helper_ignores_quoted_server(self) -> None:
        """Test is_server_command ignores quoted content."""
        service = ClaudeHookService()

        assert service.is_server_command('echo "npm run dev"') is False
        assert service.is_server_command("npm run dev") is True

    def test_helper_ignores_quoted_git_interactive(self) -> None:
        """Test is_interactive_git_command ignores quoted content."""
        service = ClaudeHookService()

        assert (
            service.is_interactive_git_command('echo "git rebase -i main"') is False
        )
        assert service.is_interactive_git_command("git rebase -i main") is True


class TestEscapedQuotes:
    """Tests for proper handling of escaped quotes in commands."""

    def test_allows_escaped_quotes_with_watch_inside(self) -> None:
        """Test that escaped quotes with 'watch' inside are handled correctly."""
        service = ClaudeHookService()
        # The word 'watch' appears inside escaped quotes - should be stripped
        hook_input = HookInput(
            tool_input={"command": 'echo "v1.0 \\"watch\\" release"'}
        )

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_allows_commit_with_escaped_quotes_containing_blocked_word(self) -> None:
        """Test commit message with escaped quotes containing blocked patterns."""
        service = ClaudeHookService()
        hook_input = HookInput(
            tool_input={
                "command": 'git commit -m "Update \\"watch\\" mode documentation"'
            }
        )

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_allows_nested_escaped_quotes_with_serve(self) -> None:
        """Test nested escaped quotes containing 'serve' keyword."""
        service = ClaudeHookService()
        hook_input = HookInput(
            tool_input={"command": 'echo "config: \\"serve\\": true"'}
        )

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_still_blocks_watch_outside_escaped_quotes(self) -> None:
        """Test that watch command outside quotes is still blocked."""
        service = ClaudeHookService()
        # 'watch' appears outside the quoted content
        hook_input = HookInput(
            tool_input={"command": 'npm run watch --config "test.json"'}
        )

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.BLOCK

    def test_handles_mixed_quote_styles(self) -> None:
        """Test handling of mixed single and double quotes."""
        service = ClaudeHookService()
        hook_input = HookInput(
            tool_input={"command": "git commit -m 'Fix \"watch\" handling'"}
        )

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_handles_backslash_at_end_of_double_quotes(self) -> None:
        """Test backslash escape at end of double-quoted string."""
        service = ClaudeHookService()
        # Escaped backslash followed by closing quote
        hook_input = HookInput(
            tool_input={"command": 'echo "path\\\\watch\\\\"'}
        )

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        assert result == HookResult.ALLOW

    def test_handles_unclosed_quotes_gracefully(self) -> None:
        """Test that unclosed quotes don't cause errors."""
        service = ClaudeHookService()
        # Unclosed double quote - everything after should be treated as quoted
        hook_input = HookInput(tool_input={"command": 'echo "watch'})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        # 'watch' is inside the unclosed quote, so should be stripped
        assert result == HookResult.ALLOW

    def test_handles_empty_escaped_quotes(self) -> None:
        """Test empty escaped quotes don't cause issues."""
        service = ClaudeHookService()
        hook_input = HookInput(tool_input={"command": 'echo "\\"\\"" watch'})

        result = service.execute_hook(HookType.SERVER_GUARD, hook_input)

        # 'watch' is outside quotes, should be blocked
        assert result == HookResult.BLOCK

    def test_is_watch_command_with_escaped_quotes(self) -> None:
        """Test is_watch_command helper with escaped quotes."""
        service = ClaudeHookService()

        # 'watch' inside escaped quotes should not match
        assert service.is_watch_command('echo "v1.0 \\"watch\\" release"') is False
        # Actual watch command should still match
        assert service.is_watch_command("npm test --watch") is True

    def test_is_server_command_with_escaped_quotes(self) -> None:
        """Test is_server_command helper with escaped quotes."""
        service = ClaudeHookService()

        # 'npm run dev' inside escaped quotes should not match
        assert service.is_server_command('echo "\\"npm run dev\\""') is False
        # Actual server command should still match
        assert service.is_server_command("npm run dev") is True
