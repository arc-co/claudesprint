/**
 * ClaudeSprint Dashboard - SSE Client
 */

class Dashboard {
    constructor() {
        this.eventSource = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.stepElapsedInterval = null;
        this.stepStartTime = null;

        // DOM elements
        this.elements = {
            connectionStatus: document.getElementById('connection-status'),
            sprintId: document.getElementById('sprint-id'),
            progressFill: document.getElementById('progress-fill'),
            progressText: document.getElementById('progress-text'),
            issueName: document.getElementById('issue-name'),
            currentStep: document.getElementById('current-step'),
            stepElapsed: document.getElementById('step-elapsed'),
            retryCount: document.getElementById('retry-count'),
            maxRetry: document.getElementById('max-retry'),
            workflowSteps: document.getElementById('workflow-steps'),
            outputContent: document.getElementById('output-content'),
            outputContainer: document.getElementById('output-container'),
            clearOutput: document.getElementById('clear-output'),
        };

        // Step order for workflow visualization
        this.stepOrder = [
            'read-docs', 'implement', 'write-tests', 'run-tests',
            'fix-tests', 'code-review', 'commit-changes'
        ];

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
            console.error('Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        setTimeout(() => this.connect(), Math.min(delay, 30000));
    }

    setConnectionStatus(status) {
        const el = this.elements.connectionStatus;
        el.className = `connection-status ${status}`;

        const textMap = {
            connecting: 'Connecting...',
            connected: 'Connected',
            disconnected: 'Disconnected',
        };

        el.querySelector('.status-text').textContent = textMap[status] || status;
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
            issue_iteration: (data) => this.onIssueIteration(data),
            step_started: (data) => this.onStepStarted(data),
            step_completed: (data) => this.onStepCompleted(data),
            step_failed: (data) => this.onStepFailed(data),
            subprocess_started: (data) => this.onSubprocessStarted(data),
            subprocess_output: (data) => this.onSubprocessOutput(data),
            subprocess_ended: () => this.onSubprocessEnded(),
            output: (data) => this.onOutput(data),
            rate_limited: () => this.addOutput('Rate limited - waiting...', 'error'),
            process_hung: (data) => this.addOutput(`Process appears hung (${data.seconds_inactive}s inactive)`, 'error'),
        };

        const handler = handlers[event.type];
        if (handler) {
            handler(event.data);
        }
    }

    updateFullState(state) {
        // Sprint info
        if (state.sprint_id) {
            this.elements.sprintId.textContent = state.sprint_id;
        }
        this.updateProgress(state.completed_issues, state.total_issues);

        // Issue info
        if (state.current_issue_id) {
            this.elements.issueName.textContent = state.current_issue_name || state.current_issue_id;
        } else {
            this.elements.issueName.textContent = 'Waiting for issue...';
        }

        // Step info
        if (state.current_step) {
            this.elements.currentStep.textContent = state.current_step;
            this.highlightStep(state.current_step);
        }

        if (state.step_start_time) {
            this.stepStartTime = new Date(state.step_start_time);
        }

        // Metrics
        this.elements.retryCount.textContent = state.retry_count || 0;
        this.elements.maxRetry.textContent = state.max_retry || 5;

        // Output
        if (state.output_lines && state.output_lines.length > 0) {
            state.output_lines.forEach(line => this.addOutput(line));
        }
    }

    updateProgress(completed, total) {
        total = total || 0;
        completed = completed || 0;

        const percentage = total > 0 ? (completed / total) * 100 : 0;
        this.elements.progressFill.style.width = `${percentage}%`;
        this.elements.progressText.textContent = `${completed}/${total}`;
    }

    onSprintStarted(data) {
        this.elements.sprintId.textContent = data.sprint_id;
        this.updateProgress(data.completed_count, data.total_count);
        this.clearAllStepStates();
    }

    onSprintCompleted(data) {
        this.updateProgress(data.completed_count, data.total_count);
        this.addOutput('Sprint completed!', 'success');
    }

    onSprintIteration(data) {
        this.updateProgress(data.completed_count, data.total_count);
    }

    onSelectingIssue() {
        this.elements.issueName.textContent = 'Selecting next issue...';
        this.elements.currentStep.textContent = 'selecting';
        this.clearAllStepStates();
    }

    onIssueStarted(data) {
        this.elements.issueName.textContent = data.issue_name || data.issue_id;
        this.elements.retryCount.textContent = '0';
        this.clearAllStepStates();
        this.elements.outputContent.innerHTML = '';
    }

    onIssueCompleted(data) {
        this.addOutput(`Issue completed: ${data.issue_id}`, 'success');
        this.elements.issueName.textContent = 'Waiting for issue...';
        this.elements.currentStep.textContent = '-';
        this.clearAllStepStates();
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
        const stepName = data.step_name;
        this.markStepCompleted(stepName);
    }

    onStepFailed(data) {
        const stepName = data.step_name;
        this.markStepFailed(stepName);
        this.elements.retryCount.textContent = data.retry_count || 0;
    }

    onSubprocessStarted(data) {
        this.addOutput(`> ${data.command}`, 'command');
    }

    onSubprocessOutput(data) {
        this.addOutput(data.line);
    }

    onSubprocessEnded() {
        // No specific action needed
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

        // Auto-scroll to bottom
        this.elements.outputContainer.scrollTop = this.elements.outputContainer.scrollHeight;
    }

    highlightStep(stepName) {
        // Clear previous states except completed
        this.elements.workflowSteps.querySelectorAll('.step').forEach(el => {
            if (!el.classList.contains('completed')) {
                el.classList.remove('active', 'failed');
            }
        });

        // Highlight current step
        const stepEl = this.elements.workflowSteps.querySelector(`[data-step="${stepName}"]`);
        if (stepEl) {
            stepEl.classList.remove('completed', 'failed');
            stepEl.classList.add('active');
        }
    }

    markStepCompleted(stepName) {
        const stepEl = this.elements.workflowSteps.querySelector(`[data-step="${stepName}"]`);
        if (stepEl) {
            stepEl.classList.remove('active', 'failed');
            stepEl.classList.add('completed');
        }
    }

    markStepFailed(stepName) {
        const stepEl = this.elements.workflowSteps.querySelector(`[data-step="${stepName}"]`);
        if (stepEl) {
            stepEl.classList.remove('active', 'completed');
            stepEl.classList.add('failed');
        }
    }

    clearAllStepStates() {
        this.elements.workflowSteps.querySelectorAll('.step').forEach(el => {
            el.classList.remove('active', 'completed', 'failed');
        });
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
        if (seconds < 60) {
            return `${seconds}s`;
        }
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}m ${secs}s`;
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});
