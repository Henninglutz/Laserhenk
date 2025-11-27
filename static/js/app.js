/**
 * LASERHENK Frontend JavaScript
 *
 * Handles workflow interaction, session management, and real-time updates
 */

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

let currentSession = {
    id: null,
    active: false,
    currentAgent: null,
    messages: []
};

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('LASERHENK App initialized');

    // Load agents
    loadAgents();

    // Setup event listeners
    setupEventListeners();
});

// ============================================================================
// EVENT LISTENERS
// ============================================================================

function setupEventListeners() {
    // Session controls
    document.getElementById('btn-new-session')?.addEventListener('click', createNewSession);
    document.getElementById('btn-start-workflow')?.addEventListener('click', startWorkflow);
    document.getElementById('btn-resume-workflow')?.addEventListener('click', resumeWorkflow);

    // Chat
    document.getElementById('btn-send')?.addEventListener('click', sendMessage);
    document.getElementById('user-input')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
}

// ============================================================================
// SESSION MANAGEMENT
// ============================================================================

async function createNewSession() {
    try {
        const response = await fetch('/LASERHENK/session/new', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        const data = await response.json();

        if (data.success) {
            currentSession.id = data.session_id;
            currentSession.active = true;

            updateSessionInfo();
            enableControls(['btn-start-workflow']);
            addMessage('system', `Session created: ${data.session_id.substring(0, 8)}...`);
        }
    } catch (error) {
        console.error('Error creating session:', error);
        addMessage('system', 'Error creating session: ' + error.message);
    }
}

async function startWorkflow() {
    if (!currentSession.active) {
        addMessage('system', 'No active session');
        return;
    }

    try {
        disableControls(['btn-start-workflow']);
        addMessage('system', 'Starting workflow...');

        const response = await fetch('/LASERHENK/workflow/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            currentSession.currentAgent = data.current_agent;
            updateAgentStatus(data.current_agent);

            // Display messages
            if (data.messages) {
                data.messages.forEach(msg => {
                    addMessage(msg.agent || 'system', msg.content);
                });
            }

            // Enable resume if workflow paused
            if (data.next_agent === null || data.messages.some(m => m.agent === 'hitl_interrupt')) {
                enableControls(['btn-resume-workflow']);
            }
        }
    } catch (error) {
        console.error('Error starting workflow:', error);
        addMessage('system', 'Error: ' + error.message);
        enableControls(['btn-start-workflow']);
    }
}

async function resumeWorkflow() {
    try {
        disableControls(['btn-resume-workflow']);
        addMessage('system', 'Resuming workflow...');

        const userInput = document.getElementById('user-input')?.value;

        const response = await fetch('/LASERHENK/workflow/resume', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_input: userInput ? { role: 'user', content: userInput } : null
            })
        });

        const data = await response.json();

        if (data.success) {
            currentSession.currentAgent = data.current_agent;

            if (data.messages) {
                data.messages.forEach(msg => {
                    addMessage(msg.agent || 'system', msg.content);
                });
            }

            document.getElementById('user-input').value = '';
        }
    } catch (error) {
        console.error('Error resuming workflow:', error);
        addMessage('system', 'Error: ' + error.message);
    }
}

// ============================================================================
// AGENTS
// ============================================================================

async function loadAgents() {
    try {
        const response = await fetch('/LASERHENK/agents');
        const data = await response.json();

        const agentList = document.getElementById('agent-list');
        if (!agentList) return;

        agentList.innerHTML = '';

        data.agents.forEach(agent => {
            const agentEl = document.createElement('div');
            agentEl.className = 'agent-item';
            agentEl.id = `agent-${agent.name.toLowerCase().replace(/\s+/g, '-')}`;
            agentEl.innerHTML = `
                <h3>${agent.name}</h3>
                <p>${agent.description}</p>
                <small>${agent.phase}</small>
            `;
            agentList.appendChild(agentEl);
        });
    } catch (error) {
        console.error('Error loading agents:', error);
    }
}

function updateAgentStatus(agentName) {
    // Remove all active classes
    document.querySelectorAll('.agent-item').forEach(el => {
        el.classList.remove('active');
    });

    // Add active to current agent
    if (agentName) {
        const agentEl = document.getElementById(`agent-${agentName.toLowerCase().replace(/\s+/g, '-')}`);
        if (agentEl) {
            agentEl.classList.add('active');
        }
    }
}

// ============================================================================
// UI UPDATES
// ============================================================================

function updateSessionInfo() {
    const sessionInfo = document.getElementById('session-id');
    if (sessionInfo && currentSession.id) {
        sessionInfo.textContent = `Session: ${currentSession.id.substring(0, 16)}...`;
    }
}

function enableControls(buttonIds) {
    buttonIds.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.disabled = false;
    });
}

function disableControls(buttonIds) {
    buttonIds.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.disabled = true;
    });
}

function addMessage(agent, content) {
    const container = document.getElementById('messages-container');
    if (!container) return;

    const messageEl = document.createElement('div');
    messageEl.className = `message ${agent}`;

    const agentLabel = agent === 'user' ? 'You' : agent.toUpperCase();
    messageEl.innerHTML = `<strong>${agentLabel}:</strong> ${escapeHtml(content)}`;

    container.appendChild(messageEl);
    container.scrollTop = container.scrollHeight;
}

function sendMessage() {
    const input = document.getElementById('user-input');
    if (!input || !input.value.trim()) return;

    const message = input.value.trim();
    addMessage('user', message);

    // Clear input
    input.value = '';

    // In a real app, send to backend
    // For now, just echo
    setTimeout(() => {
        addMessage('system', 'Message received. Use workflow controls to interact with agents.');
    }, 500);
}

// ============================================================================
// UTILITIES
// ============================================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// ERROR HANDLING
// ============================================================================

window.addEventListener('error', (e) => {
    console.error('Global error:', e.error);
});

window.addEventListener('unhandledrejection', (e) => {
    console.error('Unhandled promise rejection:', e.reason);
});
