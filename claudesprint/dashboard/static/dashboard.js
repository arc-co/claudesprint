/**
 * ClaudeSprint Dashboard - Pure TUI
 */

class Dashboard {
    constructor() {
        this.eventSource = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.stepElapsedInterval = null;
        this.stepStartTime = null;

        this.elements = {
            connStatus: document.getElementById('conn-status'),
            sprintId: document.getElementById('sprint-id'),
            issueCount: document.getElementById('issue-count'),
            issueName: document.getElementById('issue-name'),
            currentStep: document.getElementById('current-step'),
            stepElapsed: document.getElementById('step-elapsed'),
            retryCount: document.getElementById('retry-count'),
            maxRetry: document.getElementById('max-retry'),
            outputContent: document.getElementById('output-content'),
            outputContainer: document.getElementById('output-container'),
            clearOutput: document.getElementById('clear-output'),
            // Task board columns
            boardPending: document.getElementById('board-pending'),
            boardInProgress: document.getElementById('board-in-progress'),
            boardCompleted: document.getElementById('board-completed'),
            boardBlocked: document.getElementById('board-blocked'),
        };

        // Track issues for task board
        this.issues = {};

        this.stepElements = {
            'read-docs': document.getElementById('wf-docs'),
            'implement': document.getElementById('wf-impl'),
            'write-tests': document.getElementById('wf-tests'),
            'run-tests': document.getElementById('wf-run'),
            'fix-tests': document.getElementById('wf-fix'),
            'code-review': document.getElementById('wf-review'),
            'commit-changes': document.getElementById('wf-commit'),
        };

        this.stepLabels = {
            'read-docs': 'docs',
            'implement': 'impl',
            'write-tests': 'tests',
            'run-tests': 'run',
            'fix-tests': 'fix',
            'code-review': 'review',
            'commit-changes': 'commit',
        };

        this.init();
    }

    init() {
        this.connect();
        this.setupEventListeners();
        this.startElapsedTimer();
    }

    setupEventListeners() {
        this.elements.clearOutput.addEventListener('click', () => {
            this.elements.outputContent.innerHTML = '';
        });
    }

    connect() {
        this.setConnectionStatus('connecting');
        this.eventSource = new EventSource('/events');

        this.eventSource.onopen = () => {
            this.setConnectionStatus('connected');
            this.reconnectAttempts = 0;
        };

        this.eventSource.onmessage = (event) => {
            this.handleEvent(JSON.parse(event.data));
        };

        this.eventSource.onerror = () => {
            this.setConnectionStatus('disconnected');
            this.eventSource.close();
            this.scheduleReconnect();
        };
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            return;
        }
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        setTimeout(() => this.connect(), Math.min(delay, 30000));
    }

    setConnectionStatus(status) {
        const el = this.elements.connStatus;
        el.className = status;
        const text = { connecting: '...', connected: 'OK', disconnected: 'ERR' };
        el.textContent = text[status] || status;
    }

    handleEvent(event) {
        const handlers = {
            initial_state: (data) => this.updateFullState(data),
            sprint_started: (data) => this.onSprintStarted(data),
            sprint_completed: (data) => this.onSprintCompleted(data),
            sprint_iteration: (data) => this.onSprintIteration(data),
            selecting_issue: () => this.onSelectingIssue(),
            issue_started: (data) => this.onIssueStarted(data),
            issue_completed: (data) => this.onIssueCompleted(data),
            issue_failed: (data) => this.onIssueFailed(data),
            issue_iteration: (data) => this.onIssueIteration(data),
            step_started: (data) => this.onStepStarted(data),
            step_completed: (data) => this.onStepCompleted(data),
            step_failed: (data) => this.onStepFailed(data),
            subprocess_started: (data) => this.onSubprocessStarted(data),
            subprocess_output: (data) => this.onSubprocessOutput(data),
            subprocess_ended: () => {},
            output: (data) => this.onOutput(data),
            rate_limited: () => this.addOutput('RATE LIMITED', 'warning'),
            process_hung: (data) => this.addOutput(`HUNG ${data.seconds_inactive}s`, 'error'),
        };

        const handler = handlers[event.type];
        if (handler) handler(event.data);
    }

    updateFullState(state) {
        if (state.sprint_id) {
            this.elements.sprintId.textContent = state.sprint_id;
        }
        this.updateIssueCount(state.completed_issues, state.total_issues);

        if (state.current_issue_id) {
            this.elements.issueName.textContent = state.current_issue_name || state.current_issue_id;
        } else {
            this.elements.issueName.textContent = 'Waiting...';
        }

        if (state.current_step) {
            this.elements.currentStep.textContent = state.current_step;
            this.highlightStep(state.current_step);
        }

        if (state.step_start_time) {
            this.stepStartTime = new Date(state.step_start_time);
        }

        this.elements.retryCount.textContent = state.retry_count || 0;
        this.elements.maxRetry.textContent = state.max_retry || 5;

        if (state.output_lines && state.output_lines.length > 0) {
            state.output_lines.forEach(line => this.addOutput(line));
        }

        // Load issues for task board
        if (state.issues) {
            this.issues = state.issues;
            this.renderTaskBoard();
            // Highlight active issue
            if (state.current_issue_id) {
                this.highlightActiveIssue(state.current_issue_id);
            }
        }
    }

    updateIssueCount(completed, total) {
        total = total || 0;
        completed = completed || 0;
        this.elements.issueCount.textContent = `${completed}/${total}`;
    }

    onSprintStarted(data) {
        this.elements.sprintId.textContent = data.sprint_id;
        this.updateIssueCount(data.completed_count, data.total_count);
        this.clearSteps();
        // Load issues for task board
        if (data.issues) {
            this.issues = {};
            data.issues.forEach(issue => {
                this.issues[issue.id] = issue;
            });
            this.renderTaskBoard();
        }
    }

    onSprintCompleted(data) {
        this.updateIssueCount(data.completed_count, data.total_count);
        this.addOutput('SPRINT DONE', 'success');
    }

    onSprintIteration(data) {
        this.updateIssueCount(data.completed_count, data.total_count);
    }

    onSelectingIssue() {
        this.elements.issueName.textContent = 'Selecting...';
        this.elements.currentStep.textContent = '-';
        this.clearSteps();
    }

    onIssueStarted(data) {
        this.elements.issueName.textContent = data.issue_name || data.issue_id;
        this.elements.retryCount.textContent = '0';
        this.clearSteps();
        this.elements.outputContent.innerHTML = '';
        // Update task board
        this.updateIssueStatus(data.issue_id, 'in_progress');
        this.highlightActiveIssue(data.issue_id);
    }

    onIssueCompleted(data) {
        this.addOutput(`DONE: ${data.issue_id}`, 'success');
        this.elements.issueName.textContent = 'Waiting...';
        this.elements.currentStep.textContent = '-';
        this.clearSteps();
        // Update task board
        this.updateIssueStatus(data.issue_id, 'completed');
        this.clearActiveIssue();
    }

    onIssueFailed(data) {
        this.addOutput(`FAILED: ${data.issue_id}`, 'error');
        this.elements.issueName.textContent = 'Waiting...';
        this.elements.currentStep.textContent = '-';
        this.clearSteps();
        // Update task board - failed issues go back to pending
        this.updateIssueStatus(data.issue_id, 'pending');
        this.clearActiveIssue();
    }

    onIssueIteration(data) {
        this.elements.retryCount.textContent = data.retry_count || 0;
        this.elements.maxRetry.textContent = data.max_retry || 5;
    }

    onStepStarted(data) {
        const stepName = data.step_name;
        this.elements.currentStep.textContent = stepName;
        this.stepStartTime = new Date();
        this.highlightStep(stepName);
    }

    onStepCompleted(data) {
        this.clearSteps();
    }

    onStepFailed(data) {
        this.elements.retryCount.textContent = data.retry_count || 0;
        this.clearSteps();
    }

    onSubprocessStarted(data) {
        this.addOutput(`$ ${data.command}`, 'command');
    }

    onSubprocessOutput(data) {
        this.addOutput(data.line);
    }

    onOutput(data) {
        this.addOutput(data.text);
    }

    addOutput(text, type = '') {
        const line = document.createElement('span');
        line.className = `output-line ${type}`;
        line.textContent = text;
        this.elements.outputContent.appendChild(line);
        this.elements.outputContent.appendChild(document.createTextNode('\n'));
        this.elements.outputContainer.scrollTop = this.elements.outputContainer.scrollHeight;
    }

    highlightStep(stepName) {
        // Clear all steps first
        for (const [name, el] of Object.entries(this.stepElements)) {
            if (el) {
                el.classList.remove('active');
                el.textContent = `[ ] ${this.stepLabels[name]}`;
            }
        }
        // Highlight active
        const activeEl = this.stepElements[stepName];
        if (activeEl) {
            activeEl.classList.add('active');
            activeEl.textContent = `[*] ${this.stepLabels[stepName]}`;
        }
    }

    clearSteps() {
        for (const [name, el] of Object.entries(this.stepElements)) {
            if (el) {
                el.classList.remove('active');
                el.textContent = `[ ] ${this.stepLabels[name]}`;
            }
        }
        this.stepStartTime = null;
        this.elements.stepElapsed.textContent = '-';
    }

    startElapsedTimer() {
        this.stepElapsedInterval = setInterval(() => {
            if (this.stepStartTime) {
                const elapsed = Math.floor((Date.now() - this.stepStartTime.getTime()) / 1000);
                this.elements.stepElapsed.textContent = this.formatElapsed(elapsed);
            }
        }, 1000);
    }

    formatElapsed(seconds) {
        if (seconds < 60) return `${seconds}s`;
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}m${secs}s`;
    }

    // Task Board Methods

    renderTaskBoard() {
        // Clear all columns
        this.elements.boardPending.innerHTML = '';
        this.elements.boardInProgress.innerHTML = '';
        this.elements.boardCompleted.innerHTML = '';
        this.elements.boardBlocked.innerHTML = '';

        // Group issues by status
        const grouped = {
            pending: [],
            in_progress: [],
            completed: [],
            blocked: []
        };

        for (const issue of Object.values(this.issues)) {
            const status = issue.status || 'pending';
            if (grouped[status]) {
                grouped[status].push(issue);
            } else {
                grouped.pending.push(issue);
            }
        }

        // Render each column
        this.renderColumn(this.elements.boardPending, grouped.pending);
        this.renderColumn(this.elements.boardInProgress, grouped.in_progress);
        this.renderColumn(this.elements.boardCompleted, grouped.completed);
        this.renderColumn(this.elements.boardBlocked, grouped.blocked);
    }

    renderColumn(container, issues) {
        if (issues.length === 0) {
            container.innerHTML = '<div class="empty-column">-</div>';
            return;
        }

        issues.forEach(issue => {
            const card = this.createIssueCard(issue);
            container.appendChild(card);
        });
    }

    createIssueCard(issue) {
        const card = document.createElement('div');
        card.className = 'issue-card';
        card.dataset.issueId = issue.id;

        const idEl = document.createElement('div');
        idEl.className = 'issue-id';
        idEl.textContent = issue.id;

        const titleEl = document.createElement('div');
        titleEl.className = 'issue-title';
        titleEl.textContent = issue.title;
        titleEl.title = issue.title; // Show full title on hover

        const metaEl = document.createElement('div');
        metaEl.className = 'issue-meta';

        const priorityEl = document.createElement('span');
        priorityEl.className = `priority ${issue.priority || 'medium'}`;
        priorityEl.textContent = (issue.priority || 'medium').toUpperCase();

        metaEl.appendChild(priorityEl);

        if (issue.category) {
            const catEl = document.createElement('span');
            catEl.className = 'category';
            catEl.textContent = issue.category;
            metaEl.appendChild(catEl);
        }

        card.appendChild(idEl);
        card.appendChild(titleEl);
        card.appendChild(metaEl);

        return card;
    }

    updateIssueStatus(issueId, newStatus) {
        if (this.issues[issueId]) {
            this.issues[issueId].status = newStatus;
            this.renderTaskBoard();
        }
    }

    highlightActiveIssue(issueId) {
        // Remove active class from all cards
        document.querySelectorAll('.issue-card').forEach(card => {
            card.classList.remove('active');
        });
        // Add active class to current issue
        const activeCard = document.querySelector(`.issue-card[data-issue-id="${issueId}"]`);
        if (activeCard) {
            activeCard.classList.add('active');
        }
    }

    clearActiveIssue() {
        document.querySelectorAll('.issue-card').forEach(card => {
            card.classList.remove('active');
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});
