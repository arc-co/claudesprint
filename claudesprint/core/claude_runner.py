"""Claude CLI subprocess wrapper."""

import asyncio
import logging
import os
import re
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from claudesprint.utils.logging import ConversationLogger
from claudesprint.utils.process_manager import get_process_manager

# Module-level logger for debugging
logger = logging.getLogger(__name__)


@dataclass
class ClaudeResult:
    """Result of a Claude session."""

    exit_code: int
    duration_seconds: int
    timed_out: bool
    rate_limited: bool
    crashed: bool
    output: str
    error_type: str | None = None


class ClaudeRunner:
    """Wrapper for running Claude CLI sessions."""

    RATE_LIMIT_PATTERNS = [
        r"you've hit your limit",
        r"rate limit",
        r"too many requests",
        r"quota exceeded",
        r"resets.*utc",
        r"please try again later",
        r"token limit",
        r"usage limit",
        r"exceeded your.*limit",
        r"api rate limit",
    ]

    # Patterns indicating Claude CLI crashed or had unhandled errors
    CRASH_PATTERNS = [
        r"No messages returned",
        r"unhandled.*promise.*rejection",
        r"async function without a catch block",
        r"SIGKILL",
        r"SIGTERM",
        r"SIGSEGV",
        r"fatal error",
        r"panic:",
        r"Error:.*at.*native:",
        r"\$bunfs/root/claude",  # Bun runtime error location
        r"Segmentation fault",
        r"Bus error",
        r"Killed",
        r"core dumped",
    ]

    # Patterns for valid short outputs that are NOT crashes
    # These are legitimate error messages from Claude that happen to be short
    VALID_SHORT_OUTPUT_PATTERNS = [
        r"no changes",
        r"nothing to commit",
        r"up to date",
        r"already exists",
        r"permission denied",
        r"file not found",
        r"command not found",
        r"successfully",
        r"completed",
        r"done",
        r"skipping",
        r"no.*tasks",
    ]

    # Minimum output length to consider non-crash for unknown exit codes
    MIN_OUTPUT_LENGTH = 50

    def __init__(
        self,
        project_root: str | Path,
        timeout: int = 1800,  # 30 minutes default
        kill_timeout: int = 10,  # Grace period before SIGKILL
        min_output_length: int | None = None,  # Override MIN_OUTPUT_LENGTH
        common_prompt_file: str | Path | None = None,  # Prepended to all prompts
        conversation_log_file: str | Path | None = None,  # Debug conversation logging
        conversation_logger: ConversationLogger | None = None,  # Injected logger (for testing)
    ) -> None:
        self.project_root = Path(project_root)
        self.timeout = timeout
        self.kill_timeout = kill_timeout
        self.min_output_length = min_output_length or self.MIN_OUTPUT_LENGTH
        self.common_prompt_file = Path(common_prompt_file) if common_prompt_file else None
        self._rate_limit_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.RATE_LIMIT_PATTERNS
        ]
        self._crash_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.CRASH_PATTERNS
        ]
        self._valid_short_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.VALID_SHORT_OUTPUT_PATTERNS
        ]

        # Initialize conversation logger: use injected logger, create from file path, or None
        # Injected logger takes precedence over conversation_log_file
        if conversation_logger is not None:
            self.conversation_logger: ConversationLogger | None = conversation_logger
        elif conversation_log_file is not None:
            self.conversation_logger = ConversationLogger(conversation_log_file)
        else:
            self.conversation_logger = None

        # Callbacks for subprocess lifecycle
        self.on_subprocess_start: Callable[[int, str], None] | None = None
        self.on_subprocess_end: Callable[[], None] | None = None

    def _check_rate_limit(self, output: str) -> bool:
        """Check if output indicates rate limiting."""
        for pattern in self._rate_limit_patterns:
            if pattern.search(output):
                return True
        return False

    def _check_crash(self, output: str) -> tuple[bool, str | None]:
        """Check if output indicates Claude CLI crashed.

        Returns:
            Tuple of (crashed, error_type)
        """
        for pattern in self._crash_patterns:
            match = pattern.search(output)
            if match:
                return True, match.group(0)
        return False, None

    def _is_valid_short_output(self, output: str) -> bool:
        """Check if short output matches known valid patterns.

        Some legitimate Claude responses are short but not crashes.

        Args:
            output: The output to check.

        Returns:
            True if the output matches a known valid short pattern.
        """
        for pattern in self._valid_short_patterns:
            if pattern.search(output):
                return True
        return False

    def _should_mark_as_crash(
        self,
        exit_code: int,
        output: str,
        rate_limited: bool,
        explicit_crash: bool,
    ) -> tuple[bool, str | None]:
        """Determine if the result should be marked as a crash.

        Uses multiple heuristics to avoid false positives:
        1. If explicit crash pattern found, mark as crash
        2. If rate limited, don't mark as crash
        3. If exit code is 0, don't mark as crash
        4. If output is very short AND doesn't match valid patterns, mark as crash

        Args:
            exit_code: Process exit code.
            output: Full output text.
            rate_limited: Whether rate limiting was detected.
            explicit_crash: Whether explicit crash pattern was found.

        Returns:
            Tuple of (is_crash, error_type)
        """
        if explicit_crash:
            return True, "crash_pattern_detected"

        if rate_limited or exit_code == 0:
            return False, None

        stripped = output.strip()

        # Very short output with non-zero exit often indicates crash
        if len(stripped) < self.min_output_length:
            # But check if it matches known valid short patterns
            if self._is_valid_short_output(stripped):
                logger.debug(f"Short output matches valid pattern, not marking as crash")
                return False, None

            # Check for common valid exit codes with short output
            # Exit code 1 with "Aborted" or similar is not a crash
            if exit_code == 1 and any(word in stripped.lower() for word in ["abort", "cancel", "skip"]):
                return False, None

            logger.debug(f"Short output ({len(stripped)} chars) with exit code {exit_code}, marking as crash")
            return True, f"short_output_exit_{exit_code}"

        return False, None

    def _force_kill_process(
        self,
        process: subprocess.Popen,
        grace_period: int | None = None,
    ) -> None:
        """Forcefully terminate a process with grace period.

        Sends SIGTERM first, waits for grace period, then SIGKILL if needed.
        """
        if process.poll() is not None:
            return  # Already dead

        grace = grace_period if grace_period is not None else self.kill_timeout

        try:
            # Try graceful termination first
            process.terminate()
            try:
                process.wait(timeout=grace)
                return
            except subprocess.TimeoutExpired:
                pass

            # Force kill
            logger.debug(f"Force killing process {process.pid}")
            process.kill()
            # Wait briefly to reap zombie
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.warning(f"Process {process.pid} did not exit after SIGKILL")
        except OSError as e:
            logger.debug(f"Process already dead or error: {e}")

    async def _force_kill_process_async(
        self,
        process: asyncio.subprocess.Process,
        grace_period: int | None = None,
    ) -> None:
        """Forcefully terminate an async process with grace period."""
        if process.returncode is not None:
            return  # Already dead

        grace = grace_period if grace_period is not None else self.kill_timeout

        try:
            # Try graceful termination first
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=grace)
                return
            except asyncio.TimeoutError:
                pass

            # Force kill
            logger.debug(f"Force killing async process {process.pid}")
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=2)
        except asyncio.TimeoutError:
            logger.warning(f"Async process {process.pid} did not exit after SIGKILL")
        except OSError as e:
            logger.debug(f"Async process already dead or error: {e}")

    def _build_claude_command(self, model: str | None = None) -> list[str]:
        """Build the Claude CLI command with optional model flag.

        Args:
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.

        Returns:
            List of command arguments.
        """
        cmd = ["claude", "-p", "--verbose", "--dangerously-skip-permissions"]
        if model and model in ("opus", "sonnet"):
            cmd.extend(["--model", model])
        return cmd

    def _execute_session(
        self,
        prompt_content: str,
        source_name: str,
        output_file: str | Path | None = None,
        on_output: Callable[[str], None] | None = None,
        model: str | None = None,
    ) -> ClaudeResult:
        """Execute a Claude session with the given prompt content.

        This is the core execution method that handles subprocess lifecycle,
        output streaming, timeout handling, and crash detection.

        Args:
            prompt_content: The fully prepared prompt content to send to Claude.
            source_name: Name for logging purposes (e.g., "PROMPT_init.md").
            output_file: Optional file to capture output for rate limit detection.
            on_output: Optional callback for streaming output lines.
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.

        Returns:
            ClaudeResult with exit code, duration, and status flags.
        """

        import threading
        import time

        start_time = time.time()
        output_lines: list[str] = []
        reader_exception: Exception | None = None

        process_manager = get_process_manager()

        try:
            # Start Claude in its own process group for clean termination
            cmd = self._build_claude_command(model)
            logger.debug(f"Running Claude with command: {' '.join(cmd)}")
            process = subprocess.Popen(
                cmd,
                cwd=self.project_root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered for more responsive output
                start_new_session=True,  # Create new process group
            )

            # Register process for cleanup tracking
            process_manager.register_process(process)

            # Notify subprocess start
            if self.on_subprocess_start and process.pid:
                self.on_subprocess_start(process.pid, " ".join(cmd))

            # Stream output while capturing (with exception handling)
            def stream_reader() -> None:
                nonlocal reader_exception
                try:
                    assert process.stdout is not None
                    # Use readline() instead of iterating - more responsive for pipes
                    while True:
                        line = process.stdout.readline()
                        if not line:
                            break  # EOF
                        output_lines.append(line)
                        if on_output:
                            on_output(line.rstrip())
                except BrokenPipeError:
                    # Expected when process dies - not an error
                    logger.debug("Reader thread: broken pipe (process died)")
                except ValueError:
                    # Expected when stdout is closed from main thread after timeout
                    logger.debug("Reader thread: stdout closed (expected after timeout)")
                except Exception as e:
                    reader_exception = e
                    logger.warning(f"Reader thread exception: {type(e).__name__}: {e}")

            reader_thread = threading.Thread(target=stream_reader, daemon=True)
            reader_thread.start()

            # Send prompt
            assert process.stdin is not None
            try:
                process.stdin.write(prompt_content)
                process.stdin.close()
            except BrokenPipeError:
                # Claude died before reading input
                pass

            # Wait for completion with timeout
            try:
                exit_code = process.wait(timeout=self.timeout)
                timed_out = False
            except subprocess.TimeoutExpired:
                timed_out = True
                exit_code = 124  # Standard timeout exit code
                # IMPORTANT: Close stdout FIRST to unblock reader thread immediately
                # This must happen BEFORE _force_kill_process which can take up to
                # kill_timeout seconds. Otherwise the reader thread stays blocked
                # on readline() during the entire kill grace period.
                if process.stdout:
                    try:
                        process.stdout.close()
                    except Exception as e:
                        logger.debug(f"Error closing stdout after timeout: {e}")
                # Now kill the process group (reader thread is already unblocked)
                self._force_kill_process(process)

            # Wait for reader to finish, but not forever
            reader_thread.join(timeout=5)
            if reader_thread.is_alive():
                # Reader is still stuck, try closing stdout again if not already closed
                logger.debug("Reader thread stuck, force-closing stdout")
                if process.stdout and not process.stdout.closed:
                    try:
                        process.stdout.close()
                    except Exception as e:
                        logger.debug(f"Error closing stdout: {e}")
                reader_thread.join(timeout=2)
                if reader_thread.is_alive():
                    logger.warning("Reader thread still alive after force-close")

            # Unregister process now that it's done
            process_manager.unregister_process(process)

            # Notify subprocess end
            if self.on_subprocess_end:
                self.on_subprocess_end()

        except Exception as e:
            # Notify subprocess end on exception
            if self.on_subprocess_end:
                self.on_subprocess_end()
            # Ensure process is unregistered on exception
            if 'process' in locals():
                process_manager.unregister_process(process)
            return ClaudeResult(
                exit_code=1,
                duration_seconds=int(time.time() - start_time),
                timed_out=False,
                rate_limited=False,
                crashed=True,
                output=f"Error running Claude: {e}",
                error_type=str(type(e).__name__),
            )

        duration = int(time.time() - start_time)
        full_output = "".join(output_lines)

        # Write to output file if specified
        if output_file:
            Path(output_file).write_text(full_output)

        rate_limited = self._check_rate_limit(full_output)
        explicit_crash, explicit_error = self._check_crash(full_output)

        # Improved crash detection with multiple heuristics
        crashed, error_type = self._should_mark_as_crash(
            exit_code=exit_code,
            output=full_output,
            rate_limited=rate_limited,
            explicit_crash=explicit_crash,
        )
        # Preserve explicit error type if available
        if explicit_crash and explicit_error:
            error_type = explicit_error

        # Log conversation if debug mode is enabled
        if self.conversation_logger:
            self.conversation_logger.log_interaction(
                source=source_name,
                input_text=prompt_content,
                output_text=full_output,
                exit_code=exit_code,
                model=model,
                duration_seconds=duration,
            )

        return ClaudeResult(
            exit_code=exit_code,
            duration_seconds=duration,
            timed_out=timed_out,
            rate_limited=rate_limited,
            crashed=crashed,
            output=full_output,
            error_type=error_type,
        )

    def _prepare_prompt_content(
        self,
        prompt_content: str,
        context: str | None = None,
    ) -> str:
        """Prepare prompt content by optionally prepending context.

        For XML templates, common patterns are included via Jinja2 template
        inheritance ({% include '_common.xml.j2' %}) and context data is
        embedded in <artifact> tags. The common_prompt_file parameter is
        preserved for backwards compatibility but is not used with XML templates.

        Args:
            prompt_content: The base prompt content.
            context: Optional context to prepend (deprecated for XML templates).

        Returns:
            The fully prepared prompt content.
        """
        result = prompt_content

        # For backwards compatibility with legacy markdown prompts,
        # prepend common_prompt_file if configured. XML templates
        # use {% include '_common.xml.j2' %} instead.
        if self.common_prompt_file and self.common_prompt_file.exists():
            common_content = self.common_prompt_file.read_text()
            result = common_content + "\n\n---\n\n" + result

        # Prepend context if provided (deprecated for XML templates which
        # embed context via <artifact> tags in the template)
        if context:
            result = context + "\n\n" + result

        return result

    def run_prompt(
        self,
        prompt_file: str | Path,
        output_file: str | Path | None = None,
        on_output: Callable[[str], None] | None = None,
        model: str | None = None,
        context: str | None = None,
    ) -> ClaudeResult:
        """Run Claude with a prompt file synchronously.

        Args:
            prompt_file: Path to the prompt file to pipe to Claude.
            output_file: Optional file to capture output for rate limit detection.
            on_output: Optional callback for streaming output lines.
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.
            context: Optional context to prepend to the prompt content.

        Returns:
            ClaudeResult with exit code, duration, and status flags.
        """
        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            return ClaudeResult(
                exit_code=1,
                duration_seconds=0,
                timed_out=False,
                rate_limited=False,
                crashed=False,
                output=f"Prompt file not found: {prompt_path}",
            )

        prompt_content = prompt_path.read_text()
        prompt_content = self._prepare_prompt_content(prompt_content, context)

        return self._execute_session(
            prompt_content=prompt_content,
            source_name=str(prompt_path.name),
            output_file=output_file,
            on_output=on_output,
            model=model,
        )

    def run_with_content(
        self,
        prompt_content: str,
        source_name: str = "prompt",
        output_file: str | Path | None = None,
        on_output: Callable[[str], None] | None = None,
        model: str | None = None,
        context: str | None = None,
    ) -> ClaudeResult:
        """Run Claude with prompt content directly (not from a file).

        This method is useful when prompts are loaded from package resources
        via importlib.resources rather than from filesystem paths.

        Args:
            prompt_content: The prompt content to send to Claude.
            source_name: Name for logging purposes (e.g., "PROMPT_init.md").
            output_file: Optional file to capture output for rate limit detection.
            on_output: Optional callback for streaming output lines.
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.
            context: Optional context to prepend to the prompt content.

        Returns:
            ClaudeResult with exit code, duration, and status flags.
        """
        prompt_content = self._prepare_prompt_content(prompt_content, context)

        return self._execute_session(
            prompt_content=prompt_content,
            source_name=source_name,
            output_file=output_file,
            on_output=on_output,
            model=model,
        )

    async def run_prompt_async(
        self,
        prompt_file: str | Path,
        on_output: Callable[[str], None] | None = None,
        model: str | None = None,
    ) -> ClaudeResult:
        """Run Claude with a prompt file asynchronously.

        Args:
            prompt_file: Path to the prompt file to pipe to Claude.
            on_output: Optional callback for streaming output lines.
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.

        Returns:
            ClaudeResult with exit code, duration, and status flags.
        """
        import time

        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            return ClaudeResult(
                exit_code=1,
                duration_seconds=0,
                timed_out=False,
                rate_limited=False,
                crashed=False,
                output=f"Prompt file not found: {prompt_path}",
            )

        prompt_content = prompt_path.read_text()

        # Prepend common prompt content if configured
        if self.common_prompt_file and self.common_prompt_file.exists():
            common_content = self.common_prompt_file.read_text()
            prompt_content = common_content + "\n\n---\n\n" + prompt_content

        start_time = time.time()
        output_lines: list[str] = []

        process_manager = get_process_manager()

        try:
            cmd = self._build_claude_command(model)
            logger.debug(f"Running Claude async with command: {' '.join(cmd)}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_root,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,  # Create new process group
            )

            # Register process for cleanup tracking
            if process.pid:
                process_manager.register_pid(process.pid)

            # Send prompt and read output concurrently
            async def read_output():
                assert process.stdout is not None
                try:
                    async for line in process.stdout:
                        decoded = line.decode("utf-8", errors="replace")
                        output_lines.append(decoded)
                        if on_output:
                            on_output(decoded.rstrip())
                except asyncio.CancelledError:
                    logger.debug("Async reader cancelled")
                    raise
                except Exception as e:
                    logger.warning(f"Async reader exception: {type(e).__name__}: {e}")

            # Start reading
            read_task = asyncio.create_task(read_output())

            # Send prompt (handle broken pipe if Claude dies immediately)
            assert process.stdin is not None
            try:
                process.stdin.write(prompt_content.encode())
                await process.stdin.drain()
                process.stdin.close()
                await process.stdin.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass  # Claude died before reading input

            # Wait with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(read_task, process.wait(), return_exceptions=True),
                    timeout=self.timeout,
                )
                exit_code = process.returncode or 0
                timed_out = False
            except asyncio.TimeoutError:
                # Cancel the read task
                read_task.cancel()
                try:
                    await read_task
                except asyncio.CancelledError:
                    pass

                # Kill process group
                await self._force_kill_process_async(process)
                exit_code = 124
                timed_out = True

            # Unregister process now that it's done
            if process.pid:
                process_manager.unregister_pid(process.pid)

        except Exception as e:
            # Ensure process is unregistered on exception
            if 'process' in locals() and process.pid:
                process_manager.unregister_pid(process.pid)
            return ClaudeResult(
                exit_code=1,
                duration_seconds=int(time.time() - start_time),
                timed_out=False,
                rate_limited=False,
                crashed=True,
                output=f"Error running Claude: {e}",
                error_type=str(type(e).__name__),
            )

        duration = int(time.time() - start_time)
        full_output = "".join(output_lines)
        rate_limited = self._check_rate_limit(full_output)
        explicit_crash, explicit_error = self._check_crash(full_output)

        # Improved crash detection with multiple heuristics
        crashed, error_type = self._should_mark_as_crash(
            exit_code=exit_code,
            output=full_output,
            rate_limited=rate_limited,
            explicit_crash=explicit_crash,
        )
        # Preserve explicit error type if available
        if explicit_crash and explicit_error:
            error_type = explicit_error

        # Log conversation if debug mode is enabled
        if self.conversation_logger:
            self.conversation_logger.log_interaction(
                source=str(prompt_path.name),
                input_text=prompt_content,
                output_text=full_output,
                exit_code=exit_code,
                model=model,
                duration_seconds=duration,
            )

        return ClaudeResult(
            exit_code=exit_code,
            duration_seconds=duration,
            timed_out=timed_out,
            rate_limited=rate_limited,
            crashed=crashed,
            output=full_output,
            error_type=error_type,
        )

    async def stream_prompt(
        self,
        prompt_file: str | Path,
        line_timeout: int = 300,  # 5 minutes per line
        model: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream Claude output line by line with timeout protection.

        Args:
            prompt_file: Path to the prompt file.
            line_timeout: Max seconds to wait for each line (default 5 min).
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.

        Yields:
            Output lines from Claude.
        """
        import time

        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            yield f"Error: Prompt file not found: {prompt_path}"
            return

        prompt_content = prompt_path.read_text()

        # Prepend common prompt content if configured
        if self.common_prompt_file and self.common_prompt_file.exists():
            common_content = self.common_prompt_file.read_text()
            prompt_content = common_content + "\n\n---\n\n" + prompt_content

        start_time = time.time()
        process_manager = get_process_manager()

        cmd = self._build_claude_command(model)
        logger.debug(f"Streaming Claude with command: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.project_root,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )

        # Register process for cleanup tracking
        if process.pid:
            process_manager.register_pid(process.pid)

        # Send prompt (handle broken pipe)
        assert process.stdin is not None
        try:
            process.stdin.write(prompt_content.encode())
            await process.stdin.drain()
            process.stdin.close()
            await process.stdin.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            yield "Error: Claude process died before reading input"
            await self._force_kill_process_async(process)
            return

        # Stream output with timeout protection
        assert process.stdout is not None
        try:
            while True:
                # Check total timeout
                elapsed = time.time() - start_time
                if elapsed > self.timeout:
                    yield f"Error: Total timeout ({self.timeout}s) exceeded"
                    break

                # Read next line with timeout
                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=line_timeout,
                    )
                except asyncio.TimeoutError:
                    yield f"Error: No output for {line_timeout}s, assuming hang"
                    break

                if not line:
                    break  # EOF

                decoded = line.decode("utf-8", errors="replace").rstrip()
                yield decoded

                # Check for crash patterns in output
                crashed, error_type = self._check_crash(decoded)
                if crashed:
                    yield f"Error: Claude crash detected: {error_type}"
                    break

        finally:
            # Clean up process
            await self._force_kill_process_async(process)
            # Unregister from process manager
            if process.pid:
                process_manager.unregister_pid(process.pid)
