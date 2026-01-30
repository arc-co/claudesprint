"""NiceGUI UI components for the dashboard."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from claudesprint.dashboard.state import DashboardState

# Dark theme CSS matching the original TUI style
DASHBOARD_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: monospace; font-size: 12px; background: #1F1F1F; color: #BFBFBF; }
.tui { padding: 16px 24px; }
.section { border: 1px solid #444; padding: 12px 16px; margin-bottom: -1px; }
.section.header { display: flex; justify-content: space-between; background: #2a2a2a; padding: 14px 16px; }
.section-title { color: #888; font-weight: 500; margin-bottom: 8px; }
.label { color: #BFBFBF; font-weight: 500; }
.version { color: #666; margin-left: 8px; }
.row { display: flex; gap: 24px; }
.meta { margin-top: 8px; color: #BFBFBF; }

.conn-ok { color: #0db172; }
.conn-err { color: #ef6678; }
.sprint-id { color: #D77757; }
.issue-count { color: #0db172; }
.issue-name { color: #f2f2f2; font-weight: 500; }
.current-step { color: #e3e312; }
.retry-count { color: #e3e312; }

.workflow { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 0; }
.step { color: #BFBFBF; }
.step.active { color: #D77757; font-weight: 500; }
.arrow { color: #444; }

.task-board { display: flex; gap: 12px; margin-top: 8px; min-height: 120px; }
.board-column { flex: 1; border: 1px solid #444; min-width: 0; }
.column-header { background: #2a2a2a; padding: 6px 10px; color: #888; font-weight: 500; border-bottom: 1px solid #444; text-align: center; }
.column-header.pending { color: #BFBFBF; }
.column-header.in_progress { color: #e3e312; }
.column-header.completed { color: #0db172; }
.column-header.blocked { color: #ef6678; }
.column-content { padding: 8px; max-height: 400px; overflow-y: auto; }
.issue-card { background: #2a2a2a; border: 1px solid #444; padding: 6px 8px; margin-bottom: 6px; }
.issue-card.active { border-color: #D77757; }
.issue-id { color: #888; font-weight: 500; font-size: 11px; }
.issue-title { color: #BFBFBF; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }
.issue-meta { display: flex; gap: 10px; margin-top: 4px; font-size: 11px; }
.priority { color: #BFBFBF; }
.priority.critical { color: #ef6678; font-weight: 500; }
.priority.high { color: #D77757; font-weight: 500; }
.priority.medium { color: #e3e312; }
.priority.low { color: #0db172; }
.category { color: #BFBFBF; }
.empty-column { color: #444; text-align: center; padding: 12px; }

.output-container { margin-top: 8px; max-height: 300px; overflow-y: auto; border-top: 1px solid #444; padding-top: 8px; }
.output-content { font-family: monospace; font-size: 12px; color: #BFBFBF; white-space: pre-wrap; word-break: break-all; }
.output-line { display: block; }
.output-line.command { color: #D77757; }
.output-line.error { color: #ef6678; }
.output-line.success { color: #0db172; }
.output-line.warning { color: #e3e312; }

.throbber { display: inline-block; color: #D77757; font-weight: 500; min-width: 12px; }
.btn { color: #BFBFBF; cursor: pointer; margin-left: 12px; }
.btn:hover { text-decoration: underline; color: #f2f2f2; }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #1F1F1F; }
::-webkit-scrollbar-thumb { background: #444; }
"""

WORKFLOW_STEPS = [
    ("read-docs", "docs"),
    ("implement", "impl"),
    ("write-tests", "tests"),
    ("run-tests", "run"),
    ("fix-tests", "fix"),
    ("code-review", "review"),
    ("commit-changes", "commit"),
]


def create_dashboard(state: DashboardState, refresh_callbacks: dict[str, Callable[[], None]]) -> None:
    """Create the complete dashboard UI.

    Args:
        state: The dashboard state object
        refresh_callbacks: Dict mapping section names to their refresh functions
    """
    ui.add_head_html(f"<style>{DASHBOARD_CSS}</style>")

    with ui.element("div").classes("tui"):
        _create_header(state)
        _create_sprint_section(state, refresh_callbacks)
        _create_task_board(state, refresh_callbacks)
        _create_issue_section(state, refresh_callbacks)
        _create_workflow_section(state, refresh_callbacks)
        _create_output_section(state, refresh_callbacks)

    # Timer to auto-refresh elapsed time every second
    def refresh_elapsed() -> None:
        if "issue" in refresh_callbacks:
            refresh_callbacks["issue"]()

    ui.timer(1.0, refresh_elapsed)


def _create_header(_state: DashboardState) -> None:
    """Create the header section with title and connection status."""
    with ui.element("div").classes("section header"):
        ui.html('<span class="label">ClaudeSprint<span class="version">v2.0.0</span></span>', sanitize=False)
        ui.html('<span>status: <span class="conn-ok">OK</span></span>', sanitize=False)


def _create_sprint_section(state: DashboardState, refresh_callbacks: dict[str, Callable[[], None]]) -> None:
    """Create the sprint info section."""
    with ui.element("div").classes("section"):
        ui.label("sprint").classes("section-title")

        @ui.refreshable
        def render_sprint() -> None:
            with ui.element("div").classes("row"):
                ui.html(
                    f'<span>id: <span class="sprint-id">{state.sprint_id or "-"}</span></span>'
                    f'<span style="margin-left: 24px">issues: <span class="issue-count">'
                    f"{state.completed_issues}/{state.total_issues}</span></span>",
                    sanitize=False,
                )

        render_sprint()
        refresh_callbacks["sprint"] = render_sprint.refresh


def _create_task_board(state: DashboardState, refresh_callbacks: dict[str, Callable[[], None]]) -> None:
    """Create the 4-column task board."""
    with ui.element("div").classes("section"):
        ui.label("task board").classes("section-title")

        @ui.refreshable
        def render_board() -> None:
            with ui.element("div").classes("task-board"):
                for status, header_text in [
                    ("pending", "pending"),
                    ("in_progress", "in progress"),
                    ("completed", "completed"),
                    ("blocked", "blocked"),
                ]:
                    with ui.element("div").classes("board-column"):
                        ui.label(header_text).classes(f"column-header {status}")
                        with ui.element("div").classes("column-content"):
                            issues_in_column = [
                                issue for issue in state.issues.values() if issue.get("status") == status
                            ]
                            if not issues_in_column:
                                ui.label("-").classes("empty-column")
                            else:
                                for issue in issues_in_column:
                                    is_active = issue.get("id") == state.current_issue_id
                                    card_classes = "issue-card active" if is_active else "issue-card"
                                    with ui.element("div").classes(card_classes):
                                        ui.label(issue.get("id", "")).classes("issue-id")
                                        ui.label(issue.get("title", "")).classes("issue-title")
                                        with ui.element("div").classes("issue-meta"):
                                            priority = issue.get("priority", "medium")
                                            ui.label(priority.upper()).classes(f"priority {priority}")
                                            if issue.get("category"):
                                                ui.label(issue.get("category")).classes("category")

        render_board()
        refresh_callbacks["task_board"] = render_board.refresh


def _create_issue_section(state: DashboardState, refresh_callbacks: dict[str, Callable[[], None]]) -> None:
    """Create the current issue section."""
    with ui.element("div").classes("section"):
        ui.label("issue").classes("section-title")

        @ui.refreshable
        def render_issue() -> None:
            issue_text = state.current_issue_name if state.current_issue_name else "waiting..."
            ui.label(issue_text).classes("issue-name")
            with ui.element("div").classes("row meta"):
                ui.html(
                    f'<span>step: <span class="current-step">{state.current_step or "-"}</span></span>'
                    f'<span style="margin-left: 24px">elapsed: <span>{state.step_elapsed}</span></span>'
                    f'<span style="margin-left: 24px">retry: <span class="retry-count">{state.retry_count}</span>'
                    f"/{state.max_retry}</span>",
                    sanitize=False,
                )

        render_issue()
        refresh_callbacks["issue"] = render_issue.refresh


def _create_workflow_section(state: DashboardState, refresh_callbacks: dict[str, Callable[[], None]]) -> None:
    """Create the workflow pipeline visualization."""
    with ui.element("div").classes("section"):
        ui.label("workflow").classes("section-title")

        @ui.refreshable
        def render_workflow() -> None:
            with ui.element("div").classes("workflow"):
                for i, (step_id, step_label) in enumerate(WORKFLOW_STEPS):
                    if i > 0:
                        ui.label(">").classes("arrow")
                    is_active = state.current_step == step_id
                    step_classes = "step active" if is_active else "step"
                    marker = "[*]" if is_active else "[ ]"
                    ui.label(f"{marker} {step_label}").classes(step_classes)

        render_workflow()
        refresh_callbacks["workflow"] = render_workflow.refresh


def _create_output_section(state: DashboardState, refresh_callbacks: dict[str, Callable[[], None]]) -> None:
    """Create the output log section."""
    with ui.element("div").classes("section"):
        with ui.row().classes("section-title").style("display: flex; justify-content: space-between; width: 100%"):
            ui.label("output")
            clear_btn = ui.label("clear").classes("btn")

            def clear_and_refresh() -> None:
                state.clear_output()
                refresh_callbacks["output"]()

            clear_btn.on("click", clear_and_refresh)

        @ui.refreshable
        def render_output() -> None:
            with ui.element("div").classes("output-container"), ui.element("pre").classes("output-content"):
                for line in state.output_lines:
                    # Determine line type for styling
                    line_class = "output-line"
                    if line.startswith("$ ") or line.startswith("> "):
                        line_class = "output-line command"
                    elif "error" in line.lower() or "failed" in line.lower():
                        line_class = "output-line error"
                    elif "success" in line.lower() or "done" in line.lower():
                        line_class = "output-line success"
                    elif "warning" in line.lower() or "rate limit" in line.lower():
                        line_class = "output-line warning"
                    ui.label(line + "\n").classes(line_class)

        render_output()
        refresh_callbacks["output"] = render_output.refresh
