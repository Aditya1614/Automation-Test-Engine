import sys
file = r'c:\DWH\Playwright\templates\index.html'
with open(file, 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace("'/api/flows//history'", "`/api/flows/${currentFlowId}/history`")
c = c.replace("'/api/flows//history/clear'", "`/api/flows/${currentFlowId}/history/clear`")
c = c.replace("'/api/flows//test-cases'", "`/api/flows/${currentFlowId}/test-cases`")
c = c.replace("'/api/flows//saved-flows'", "`/api/flows/${currentFlowId}/saved-flows`")
c = c.replace("'/api/flows//upload-excel'", "`/api/flows/${currentFlowId}/upload-excel`")
c = c.replace("'/api/flows//test-cases/merge'", "`/api/flows/${currentFlowId}/test-cases/merge`")
c = c.replace("'/api/flows//run'", "`/api/flows/${currentFlowId}/run`")
c = c.replace("'/api/flows//save-flow'", "`/api/flows/${currentFlowId}/save-flow`")
c = c.replace("`/api/flows//saved-flow/${tcId}`", "`/api/flows/${currentFlowId}/saved-flow/${tcId}`")
c = c.replace("`/api/flows//history/${index}`", "`/api/flows/${currentFlowId}/history/${index}`")

# Also add the new JS variables at the beginning of the script tag
script_start = '''    <script>
        // --- Auth & Flow Management ---
        const flowSelector = document.getElementById('flowSelector');
        const newFlowBtn = document.getElementById('newFlowBtn');
        const logoutBtn = document.getElementById('logoutBtn');
        const userNameDisplay = document.getElementById('userNameDisplay');
        const newFlowModal = document.getElementById('newFlowModal');
        const createFlowSubmitBtn = document.getElementById('createFlowSubmitBtn');

        let currentFlowId = sessionStorage.getItem('currentFlowId');
        let currentUser = null;

        async function initApp() {
            try {
                const res = await fetch('/api/me');
                if (!res.ok) {
                    window.location.href = '/login';
                    return;
                }
                currentUser = await res.json();
                userNameDisplay.textContent = currentUser.display_name || currentUser.username;
                
                await fetchFlows();
            } catch(e) {
                window.location.href = '/login';
            }
        }

        async function fetchFlows() {
            try {
                const res = await fetch('/api/flows');
                const flows = await res.json();
                flowSelector.innerHTML = '';
                flows.forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.id;
                    opt.textContent = f.name;
                    flowSelector.appendChild(opt);
                });
                
                if (!currentFlowId && flows.length > 0) {
                    currentFlowId = 'other';
                    if (!flows.some(f => f.id === currentFlowId)) {
                        currentFlowId = flows[0].id;
                    }
                    sessionStorage.setItem('currentFlowId', currentFlowId);
                }
                
                if (currentFlowId) {
                    flowSelector.value = currentFlowId;
                }
                
                loadFlowData();
            } catch(e) {
                console.error("Failed to fetch flows", e);
            }
        }

        function loadFlowData() {
            if (!currentFlowId) return;
            fetchTestCases();
            fetchSavedFlows();
            fetchHistory();
        }

        if (flowSelector) {
            flowSelector.addEventListener('change', (e) => {
                currentFlowId = e.target.value;
                sessionStorage.setItem('currentFlowId', currentFlowId);
                loadFlowData();
            });
        }

        if (logoutBtn) {
            logoutBtn.addEventListener('click', async () => {
                await fetch('/api/logout', { method: 'POST' });
                sessionStorage.removeItem('currentFlowId');
                window.location.href = '/login';
            });
        }

        if (newFlowBtn) {
            newFlowBtn.addEventListener('click', () => {
                document.getElementById('newFlowName').value = '';
                document.getElementById('newFlowError').style.display = 'none';
                newFlowModal.classList.remove('hidden');
            });
        }

        if (createFlowSubmitBtn) {
            createFlowSubmitBtn.addEventListener('click', async () => {
                const name = document.getElementById('newFlowName').value.trim();
                const errDiv = document.getElementById('newFlowError');
                if (!name) {
                    errDiv.textContent = 'Name is required';
                    errDiv.style.display = 'block';
                    return;
                }
                
                try {
                    const res = await fetch('/api/flows', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ name })
                    });
                    const data = await res.json();
                    if (data.error) throw new Error(data.error);
                    
                    newFlowModal.classList.add('hidden');
                    currentFlowId = data.flow.id;
                    sessionStorage.setItem('currentFlowId', currentFlowId);
                    await fetchFlows();
                } catch(e) {
                    errDiv.textContent = e.message;
                    errDiv.style.display = 'block';
                }
            });
        }
'''
if "// --- Auth & Flow Management ---" not in c:
    c = c.replace("    <script>", script_start)

# Replace the calls at the bottom
init_calls = '''        // Init
        fetchTestCases();
        fetchSavedFlows();
        fetchHistory();'''
if init_calls in c:
    c = c.replace(init_calls, "        initApp();")

with open(file, 'w', encoding='utf-8') as f:
    f.write(c)
