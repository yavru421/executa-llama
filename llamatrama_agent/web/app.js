// Constants
const DEVICE_URL = '/devices';
const STATUS_URL = '/status';
const TAILNET_DEVICES_URL = '/devices';
const FILETREE_URL = '/filetree';
const SESSION_LOG_URL = '/session-log';

// Error handling
async function handleError(error) {
    console.error(error);
    // Display a more user-friendly error message
    const el = document.getElementById('error-message');
    if (el) el.innerText = 'An error occurred. Please try again later.';
}

// Load devices
async function loadDevices() {
    try {
    const response = await fetch(DEVICE_URL, { credentials: 'include' });
        const devices = await response.json();
        const sel = document.getElementById('device-select');
        if (sel) {
            sel.innerHTML = '';
            devices.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d.ip || d;
                opt.innerText = d.name || d.ip || d;
                sel.appendChild(opt);
            });
        }
    updateWorkflowState();
    // Clear plan, approval, output, and errors on device change
    const out = document.getElementById('coursecheck-output');
    if (out) out.innerHTML = '';
    const approvalPanel = document.getElementById('approval-panel');
    if (approvalPanel) approvalPanel.style.display = 'none';
    const plannedCommand = document.getElementById('planned-command');
    if (plannedCommand) plannedCommand.innerText = '';
    const sshOut = document.getElementById('ssh-output');
    if (sshOut) sshOut.innerText = '';
    const planError = document.getElementById('plan-error');
    if (planError) planError.innerText = '';
    const approveError = document.getElementById('approve-error');
    if (approveError) approveError.innerText = '';
    } catch (error) {
        await handleError(error);
    }
}

// Load tailnet devices
async function loadTailnetDevices() {
    try {
    const response = await fetch(TAILNET_DEVICES_URL, { credentials: 'include' });
        const devices = await response.json();
        const sel = document.getElementById('tailnet-device-select');
        if (sel) {
            sel.innerHTML = '';
            devices.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d.ip || d;
                opt.innerText = d.name || d.ip || d;
                sel.appendChild(opt);
            });
        }
        updateWorkflowState();
    } catch (error) {
        await handleError(error);
    }
}

// Load file tree
async function loadFileTree(deviceIp, path, sshUser) {
    try {
        const query = `${FILETREE_URL}?device=${encodeURIComponent(deviceIp)}&path=${encodeURIComponent(path)}${sshUser ? `&ssh_user=${encodeURIComponent(sshUser)}` : ''}`;
    const response = await fetch(query, { credentials: 'include' });
        const data = await response.json();
        // ...
    } catch (error) {
        await handleError(error);
    }
}

// Load session log
async function loadSessionLog() {
    try {
    const response = await fetch(SESSION_LOG_URL, { credentials: 'include' });
        const data = await response.json();
        // ...
    } catch (error) {
        await handleError(error);
    }
}

// ...
    // Login handling + CourseCheck handler
    document.addEventListener('DOMContentLoaded', async () => {
    // Use cookie-based auth; do not persist tokens in localStorage
    window.token = null;
        const loginPanel = document.getElementById('login-panel');
        const dashboard = document.getElementById('dashboard');
        const logoutBtn = document.getElementById('logout-btn');

        function showDashboard() {
            if (loginPanel) loginPanel.style.display = 'none';
            if (dashboard) dashboard.style.display = '';
            // load devices when dashboard shows
            loadDevices();
            loadTailnetDevices();
        }

        function showLogin() {
            if (loginPanel) loginPanel.style.display = 'block';
            if (dashboard) dashboard.style.display = 'none';
        }

        // Probe /me to see if authenticated via cookie
        try {
            const meResp = await fetch('/me', { credentials: 'include' });
            if (meResp.ok) {
                showDashboard();
            } else {
                showLogin();
            }
        } catch (e) {
            showLogin();
        }

        // Login form submit
        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const user = document.getElementById('username').value;
                const pw = document.getElementById('password').value;
                const err = document.getElementById('login-error');
                try {
                    const form = new FormData();
                    form.append('username', user);
                    form.append('password', pw);
                    // Include credentials so the server can set/read cookies
                    const resp = await fetch('/login', { method: 'POST', body: form, credentials: 'include' });
                    const j = await resp.json();
                    if (resp.ok) {
                        window.token = true; // flag authenticated
                        showDashboard();
                    } else {
                        err.innerText = j.detail || 'Login failed';
                    }
                } catch (e) {
                    console.error(e);
                    err.innerText = 'Login error';
                }
            });
        }

        // Simple workflow state helper
        function updateWorkflowState() {
            const deviceSel = document.getElementById('device-select');
            const courseBtn = document.getElementById('coursecheck-btn');
            const approvePanel = document.getElementById('approval-panel');
            const approveBtn = document.getElementById('approve-btn');
            const approveVisible = approvePanel && approvePanel.style.display !== 'none';

            const deviceSelected = deviceSel && deviceSel.value;
            if (courseBtn) courseBtn.disabled = !deviceSelected;
            // Approve button enabled only if there's a planned command
            const planned = document.getElementById('planned-command') ? document.getElementById('planned-command').innerText.trim() : '';
            if (approveBtn) approveBtn.disabled = !planned;
            // Show a hint in status panel
            const statusPanel = document.getElementById('status-panel');
            if (statusPanel) {
                if (!deviceSelected) statusPanel.innerText = 'Select a device to enable planning and execution.';
                else statusPanel.innerText = 'Device selected. You may run CourseCheck.';
            }
            // Update breadcrumbs based on state
            const crumbs = [];
            crumbs.push({ label: 'Dashboard', href: '#' });
            crumbs.push({ label: 'Devices', href: '#' });
            if (deviceSelected) crumbs.push({ label: deviceSel.options[deviceSel.selectedIndex].text, href: '#' });
            // If there's a planned command, show CourseCheck/Approve states
            const plannedText = document.getElementById('planned-command') ? document.getElementById('planned-command').innerText.trim() : '';
            if (plannedText) {
                crumbs.push({ label: 'CourseCheck', href: '#' });
                crumbs.push({ label: 'Approve', href: '#' });
            } else {
                crumbs.push({ label: 'CourseCheck', href: '#' });
            }
            renderBreadcrumbs(crumbs);
        }

        function renderBreadcrumbs(items) {
            const nav = document.getElementById('breadcrumb-nav');
            if (!nav) return;
            nav.innerHTML = '';
            items.forEach((it, idx) => {
                const li = document.createElement('li');
                li.className = 'breadcrumb-item';
                if (idx === items.length - 1) {
                    li.className = 'breadcrumb-item active';
                    li.setAttribute('aria-current', 'page');
                    li.innerText = it.label;
                } else {
                    const a = document.createElement('a');
                    a.href = it.href || '#';
                    a.innerText = it.label;
                    a.addEventListener('click', (e) => {
                        e.preventDefault();
                        // Simple navigation: if user clicks Devices go to device select; if Dashboard, scroll to top
                        if (it.label === 'Devices') {
                            const sel = document.getElementById('device-select');
                            if (sel) sel.focus();
                        }
                        if (it.label === 'Dashboard') window.scrollTo({ top: 0, behavior: 'smooth' });
                    });
                    li.appendChild(a);
                }
                nav.appendChild(li);
            });
        }

        // When device selection changes, update state and clear outputs
        const deviceSelectEl = document.getElementById('device-select');
        if (deviceSelectEl) {
            deviceSelectEl.addEventListener('change', () => {
                updateWorkflowState();
                // Clear outputs and errors on device change
                const out = document.getElementById('coursecheck-output');
                if (out) out.innerHTML = '';
                const approvalPanel = document.getElementById('approval-panel');
                if (approvalPanel) approvalPanel.style.display = 'none';
                const plannedCommand = document.getElementById('planned-command');
                if (plannedCommand) plannedCommand.innerText = '';
                const sshOut = document.getElementById('ssh-output');
                if (sshOut) sshOut.innerText = '';
                const planError = document.getElementById('plan-error');
                if (planError) planError.innerText = '';
                const approveError = document.getElementById('approve-error');
                if (approveError) approveError.innerText = '';
            });
        }

        if (logoutBtn) {
            logoutBtn.addEventListener('click', async () => {
                try {
                    await fetch('/logout', { method: 'POST', credentials: 'include' });
                } catch (e) { console.error(e); }
                window.token = null;
                showLogin();
            });
        }

        // Wire change-password button quick prompt
        const changePwd = document.getElementById('change-password-btn');
        if (changePwd) {
            changePwd.addEventListener('click', async () => {
                const newPw = prompt('Enter new admin password:');
                if (!newPw) return;
                try {
                    const resp = await fetch('/set_password', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${window.token}` }, body: JSON.stringify({ new_password: newPw }) });
                    const j = await resp.json();
                    alert(j.detail || j.error || 'Changed');
                } catch (e) { console.error(e); alert('Failed'); }
            });
        }

        const btn = document.getElementById('coursecheck-btn');
        const out = document.getElementById('coursecheck-output');
        const planError = document.getElementById('plan-error');
        if (btn) {
            btn.addEventListener('click', async () => {
                try {
                    // enforce device selection
                    const ds = document.getElementById('device-select');
                    if (ds && !ds.value) {
                        if (out) out.innerText = '';
                        if (planError) planError.innerText = 'Please select a device first.';
                        return;
                    }
                    if (planError) planError.innerText = '';
                    if (out) out.innerHTML = '<em>Planning...</em>';
                    // Use a default conversation for now (could be improved)
                    const conversation = 'List files in /home/pi';
                    const resp = await fetch('/course-check', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ conversation }),
                        credentials: 'include'
                    });
                    const data = await resp.json();
                    if (data && data.plan) {
                        const list = document.createElement('ol');
                        data.plan.forEach((item, idx) => {
                            const li = document.createElement('li');
                            const p = document.createElement('div');
                            p.innerHTML = '<strong>Prompt:</strong> ' + (item.prompt || '');
                            const a = document.createElement('div');
                            a.innerHTML = '<strong>Action:</strong> ' + (item.action || '');
                            li.appendChild(p);
                            li.appendChild(a);
                            list.appendChild(li);
                        });
                        if (out) {
                            out.innerHTML = '';
                            out.appendChild(list);
                        }
                        // After rendering plan, show approval panel with first planned command
                        const first = data.plan[0] || null;
                        const approvalPanel = document.getElementById('approval-panel');
                        if (first && approvalPanel) {
                            approvalPanel.style.display = '';
                            const reasoning = document.getElementById('reasoning');
                            const plannedCommand = document.getElementById('planned-command');
                            if (reasoning) reasoning.innerText = first.prompt || '';
                            if (plannedCommand) plannedCommand.innerText = first.action || '';
                        }
                        updateWorkflowState();
                    } else {
                        if (out) out.innerText = '';
                        if (planError) planError.innerText = data.error ? ('Error: ' + data.error + '\nRaw:\n' + (data.raw||'')) : JSON.stringify(data);
                    }
                } catch (err) {
                    console.error(err);
                    if (out) out.innerText = '';
                    if (planError) planError.innerText = 'Error running CourseCheck.';
                }
            });
        }

        // Approve & Execute handler
        const approveBtn = document.getElementById('approve-btn');
        const approveError = document.getElementById('approve-error');
        if (approveBtn) {
            approveBtn.addEventListener('click', async () => {
                const cmd = document.getElementById('planned-command').innerText;
                if (!cmd) return;
                approveBtn.disabled = true;
                approveBtn.innerText = 'Executing...';
                if (approveError) approveError.innerText = '';
                try {
                    const form = new FormData();
                    form.append('action', 'ssh:' + cmd);
                    const resp = await fetch('/course-run', { method: 'POST', body: form, credentials: 'include' });
                    const j = await resp.json();
                    const sshOut = document.getElementById('ssh-output');
                    if (sshOut) sshOut.innerText = j.output || j.error || JSON.stringify(j);
                    if (j.status !== 'ok' && approveError) approveError.innerText = j.error || 'Command failed.';
                } catch (e) {
                    console.error(e);
                    if (approveError) approveError.innerText = 'Error executing command.';
                } finally {
                    approveBtn.disabled = false;
                    approveBtn.innerText = 'Approve & Execute';
                }
            });
        }

        // Load session log on dashboard show
        async function refreshSessionLog() {
            try {
                const resp = await fetch('/session-log', { credentials: 'include' });
                const data = await resp.json();
                const logDiv = document.getElementById('session-log');
                if (logDiv && data && data.log && data.log.length) {
                    logDiv.innerText = data.log[0];
                }
            } catch (e) { /* ignore */ }
        }
        refreshSessionLog();
    });
