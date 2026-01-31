"""Claude CLI subprocess wrapper."""

import asyncio
import logging
import os
import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from claudesprint.utils.logging import ConversationLogger
from claudesprint.utils.process_manager import get_process_manager

# Module-level logger for debugging
logger = logging.getLogger(__name__)


class FailureCategory(StrEnum):
    """Categories of failure for Claude CLI execution."""

    NONE = "none"  # Success (exit_code == 0)
    RATE_LIMITED = "rate_limited"  # Rate limit hit
    TIMEOUT = "timeout"  # exit_code == 124
    REJECTED = "rejected"  # Claude refused task (exit 1)
    SYSTEM_ERROR = "system_error"  # Actual crash (signal death, exit >= 128)


@dataclass
class ClaudeResult:
    """Result of a Claude session."""

    exit_code: int
    duration_seconds: int
    timed_out: bool
    rate_limited: bool
    output: str
    failure_category: FailureCategory = FailureCategory.NONE
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

    # Diagnostic patterns for logging/debugging - NOT used for crash decisions
    # Exit code is the primary determinant of crash status
    DIAGNOSTIC_PATTERNS = [
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

    # Default grace period before SIGKILL
    DEFAULT_KILL_TIMEOUT = 10

    def __init__(
        self,
        project_root: str | Path,
        timeout: int = 1800,  # 30 minutes default
        kill_timeout: int | None = None,  # Grace period before SIGKILL (from config)
        conversation_log_file: str | Path | None = None,  # Debug conversation logging
        conversation_logger: ConversationLogger | None = None,  # Injected logger (for testing)
    ) -> None:
        self.project_root = Path(project_root)
        self.timeout = timeout
        self.kill_timeout = kill_timeout if kill_timeout is not None else self.DEFAULT_KILL_TIMEOUT
        self._rate_limit_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.RATE_LIMIT_PATTERNS
        ]
        self._diagnostic_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DIAGNOSTIC_PATTERNS
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

    def _check_diagnostic(self, output: str) -> str | None:
        """Check output for diagnostic patterns (for logging only).

        This is NOT used for crash determination - exit code is authoritative.
        Returns the matched pattern for logging/debugging purposes.

        Returns:
            The matched diagnostic pattern or None.
        """
        for pattern in self._diagnostic_patterns:
            match = pattern.search(output)
            if match:
                return match.group(0)
        return None

    def _categorize_failure(
        self,
        exit_code: int,
        rate_limited: bool,
        timed_out: bool,
    ) -> tuple[FailureCategory, str | None]:
        """Categorize failure based primarily on exit code.

        Exit code is the authoritative source for crash determination:
        - Exit code 0 = SUCCESS (never a crash)
        - Exit code >= 128 = SYSTEM_ERROR (killed by signal)
        - Exit code 124 = TIMEOUT
        - Rate limited = RATE_LIMITED
        - Exit code 1 = REJECTED (normal failure, not crash)

        Args:
            exit_code: Process exit code.
            rate_limited: Whether rate limiting was detected.
            timed_out: Whether the process timed out.

        Returns:
            Tuple of (FailureCategory, error_type for logging)
        """
        if exit_code == 0:
            return FailureCategory.NONE, None

        if timed_out or exit_code == 124:
            return FailureCategory.TIMEOUT, "timeout"

        if rate_limited:
            return FailureCategory.RATE_LIMITED, "rate_limited"

        # Exit code >= 128 means killed by signal (128 + signal_number)
        if exit_code >= 128:
            signal_num = exit_code - 128
            return FailureCategory.SYSTEM_ERROR, f"signal_{signal_num}"

        # Exit code 1-127: Normal failure (Claude refused, validation failed, etc.)
        return FailureCategory.REJECTED, f"exit_{exit_code}"


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
            source_name: Name for logging purposes (e.g., "PROMPT_init.xml.j2").
            output_file: Optional file to capture output for rate limit detection.
            on_output: Optional callback for streaming output lines.
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.

        Returns:
            ClaudeResult with exit code, duration, and status flags.
        """

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

            # Stream output while capturing
            # Note: Crash detection is now done via exit code, not pattern matching
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
            poll_interval = 1.0  # Check every second
            elapsed_wait = 0.0
            timed_out = False
            exit_code = None

            while exit_code is None and elapsed_wait < self.timeout:
                # Poll process status
                exit_code = process.poll()
                if exit_code is not None:
                    break

                time.sleep(poll_interval)
                elapsed_wait += poll_interval

            # Handle timeout case
            if exit_code is None:
                timed_out = True
                exit_code = 124  # Standard timeout exit code

            # If we need to kill the process (timeout or crash didn't exit cleanly)
            if process.poll() is None:
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
                failure_category=FailureCategory.SYSTEM_ERROR,
                output=f"Error running Claude: {e}",
                error_type=str(type(e).__name__),
            )

        duration = int(time.time() - start_time)
        full_output = "".join(output_lines)

        # Write to output file if specified
        if output_file:
            Path(output_file).write_text(full_output)

        rate_limited = self._check_rate_limit(full_output)

        # Exit-code-first failure categorization
        failure_category, error_type = self._categorize_failure(
            exit_code=exit_code,
            rate_limited=rate_limited,
            timed_out=timed_out,
        )

        # Check for diagnostic patterns (logging only, not for decision-making)
        diagnostic_match = self._check_diagnostic(full_output)
        if diagnostic_match:
            logger.debug(f"Diagnostic pattern found in output: {diagnostic_match}")
            # Include diagnostic info in error_type if we have a failure
            if failure_category != FailureCategory.NONE and error_type:
                error_type = f"{error_type}:{diagnostic_match}"

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
            failure_category=failure_category,
            output=full_output,
            error_type=error_type,
        )

    async def _execute_session_async(
        self,
        prompt_content: str,
        source_name: str,
        output_file: str | Path | None = None,
        on_output: Callable[[str], None] | None = None,
        model: str | None = None,
    ) -> ClaudeResult:
        """Execute a Claude session asynchronously (primary async implementation).

        This is the async core execution method using asyncio.create_subprocess_exec().
        No background threads are used - output is read via async iteration.

        Args:
            prompt_content: The fully prepared prompt content to send to Claude.
            source_name: Name for logging purposes (e.g., "PROMPT_init.xml.j2").
            output_file: Optional file to capture output for rate limit detection.
            on_output: Optional callback for streaming output lines.
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.

        Returns:
            ClaudeResult with exit code, duration, and status flags.
        """
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

            # Notify subprocess start
            if self.on_subprocess_start and process.pid:
                self.on_subprocess_start(process.pid, " ".join(cmd))

            # Read output asynchronously (no thread needed)
            async def read_output() -> None:
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

            # Start reading task
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
            timed_out = False
            try:
                await asyncio.wait_for(
                    asyncio.gather(read_task, process.wait(), return_exceptions=True),
                    timeout=self.timeout,
                )
                exit_code = process.returncode or 0
            except asyncio.TimeoutError:
                timed_out = True
                # Cancel the read task
                read_task.cancel()
                try:
                    await read_task
                except asyncio.CancelledError:
                    pass

                # Kill process group
                await self._force_kill_process_async(process)
                exit_code = 124

            # Unregister process now that it's done
            if process.pid:
                process_manager.unregister_pid(process.pid)

            # Notify subprocess end
            if self.on_subprocess_end:
                self.on_subprocess_end()

        except Exception as e:
            # Notify subprocess end on exception
            if self.on_subprocess_end:
                self.on_subprocess_end()
            # Ensure process is unregistered on exception
            if 'process' in locals() and process.pid:
                process_manager.unregister_pid(process.pid)
            return ClaudeResult(
                exit_code=1,
                duration_seconds=int(time.time() - start_time),
                timed_out=False,
                rate_limited=False,
                failure_category=FailureCategory.SYSTEM_ERROR,
                output=f"Error running Claude: {e}",
                error_type=str(type(e).__name__),
            )

        duration = int(time.time() - start_time)
        full_output = "".join(output_lines)

        # Write to output file if specified
        if output_file:
            Path(output_file).write_text(full_output)

        rate_limited = self._check_rate_limit(full_output)

        # Exit-code-first failure categorization
        failure_category, error_type = self._categorize_failure(
            exit_code=exit_code,
            rate_limited=rate_limited,
            timed_out=timed_out,
        )

        # Check for diagnostic patterns (logging only)
        diagnostic_match = self._check_diagnostic(full_output)
        if diagnostic_match:
            logger.debug(f"Diagnostic pattern found in output: {diagnostic_match}")
            if failure_category != FailureCategory.NONE and error_type:
                error_type = f"{error_type}:{diagnostic_match}"

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
            failure_category=failure_category,
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
        embedded in <artifact> tags.

        Args:
            prompt_content: The base prompt content.
            context: Optional context to prepend (deprecated for XML templates).

        Returns:
            The fully prepared prompt content.
        """
        if context:
            return context + "\n\n" + prompt_content
        return prompt_content

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
                failure_category=FailureCategory.REJECTED,
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

    async def run_with_content_async(
        self,
        prompt_content: str,
        source_name: str = "prompt",
        output_file: str | Path | None = None,
        on_output: Callable[[str], None] | None = None,
        model: str | None = None,
        context: str | None = None,
    ) -> ClaudeResult:
        """Run Claude with prompt content directly (async version).

        This is the primary async method for running Claude with content.
        Uses asyncio subprocess handling - no background threads.

        Args:
            prompt_content: The prompt content to send to Claude.
            source_name: Name for logging purposes (e.g., "PROMPT_init.xml.j2").
            output_file: Optional file to capture output for rate limit detection.
            on_output: Optional callback for streaming output lines.
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.
            context: Optional context to prepend to the prompt content.

        Returns:
            ClaudeResult with exit code, duration, and status flags.
        """
        prompt_content = self._prepare_prompt_content(prompt_content, context)

        return await self._execute_session_async(
            prompt_content=prompt_content,
            source_name=source_name,
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
        """Run Claude with prompt content directly (sync wrapper).

        This method is useful when prompts are loaded from package resources
        via importlib.resources rather than from filesystem paths.

        For async callers, prefer run_with_content_async() to avoid event loop issues.

        Args:
            prompt_content: The prompt content to send to Claude.
            source_name: Name for logging purposes (e.g., "PROMPT_init.xml.j2").
            output_file: Optional file to capture output for rate limit detection.
            on_output: Optional callback for streaming output lines.
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.
            context: Optional context to prepend to the prompt content.

        Returns:
            ClaudeResult with exit code, duration, and status flags.
        """
        # Check if we're in an existing event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # We're already in an async context - can't use asyncio.run()
            # Fall back to the threading-based sync implementation
            prompt_content = self._prepare_prompt_content(prompt_content, context)
            return self._execute_session(
                prompt_content=prompt_content,
                source_name=source_name,
                output_file=output_file,
                on_output=on_output,
                model=model,
            )

        # Not in an event loop - use asyncio.run() with async implementation
        return asyncio.run(
            self.run_with_content_async(
                prompt_content=prompt_content,
                source_name=source_name,
                output_file=output_file,
                on_output=on_output,
                model=model,
                context=context,
            )
        )

    async def run_prompt_async(
        self,
        prompt_file: str | Path,
        on_output: Callable[[str], None] | None = None,
        model: str | None = None,
    ) -> ClaudeResult:
        """Run Claude with a prompt file asynchronously.

        Uses the async execution method - no background threads.

        Args:
            prompt_file: Path to the prompt file to pipe to Claude.
            on_output: Optional callback for streaming output lines.
            model: Model to use ("opus" or "sonnet"). If None, uses CLI default.

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
                failure_category=FailureCategory.REJECTED,
                output=f"Prompt file not found: {prompt_path}",
            )

        prompt_content = prompt_path.read_text()

        return await self._execute_session_async(
            prompt_content=prompt_content,
            source_name=str(prompt_path.name),
            on_output=on_output,
            model=model,
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
        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            yield f"Error: Prompt file not found: {prompt_path}"
            return

        prompt_content = prompt_path.read_text()

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

                # Check for diagnostic patterns (for logging info only)
                diagnostic_match = self._check_diagnostic(decoded)
                if diagnostic_match:
                    logger.debug(f"Diagnostic pattern in stream: {diagnostic_match}")

        finally:
            # Clean up process
            await self._force_kill_process_async(process)
            # Unregister from process manager
            if process.pid:
                process_manager.unregister_pid(process.pid)
