import os

file_path = r'c:\DWH\Playwright\templates\index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

modal_html = """
    <!-- Odoo User List Modal -->
    <div id="userListModal" class="modal hidden">
        <div class="modal-content" style="width: 900px; height: 70vh; display: flex; flex-direction: column;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 16px; margin-bottom: 16px;">
                <h2 style="margin: 0; color: var(--primary);">Odoo Users <span id="userListFlowName" style="font-size: 16px; color: var(--text-muted); font-weight: normal; margin-left: 8px;"></span></h2>
                <button class="btn btn-sm btn-danger" onclick="document.getElementById('userListModal').classList.add('hidden')">✕ Close</button>
            </div>
            <div style="display: flex; gap: 24px; flex: 1; overflow: hidden;">
                <!-- Groups Sidebar -->
                <div style="width: 250px; border-right: 1px solid var(--border-color); display: flex; flex-direction: column;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-right: 12px;">
                        <h4 style="margin: 0;">Groups</h4>
                        <button class="btn btn-sm btn-success" onclick="openNewGroupForm()" style="padding: 2px 8px; font-size: 12px;">+ Add</button>
                    </div>
                    <div id="newGroupForm" style="display: none; margin-bottom: 12px; padding-right: 12px;">
                        <input type="text" id="newGroupName" placeholder="Group Name" style="width: 100%; padding: 6px; border-radius: 4px; border: 1px solid var(--border-color); background: rgba(0,0,0,0.3); color: white; font-size: 12px; margin-bottom: 4px; box-sizing: border-box;" />
                        <div style="display: flex; gap: 4px;">
                            <button class="btn btn-sm btn-success" style="flex: 1; padding: 4px;" onclick="submitNewGroup()">Save</button>
                            <button class="btn btn-sm" style="flex: 1; padding: 4px;" onclick="document.getElementById('newGroupForm').style.display='none'">Cancel</button>
                        </div>
                    </div>
                    <div id="userGroupList" style="flex: 1; overflow-y: auto; padding-right: 12px;">
                        <!-- JS populated -->
                    </div>
                </div>
                <!-- Users Table -->
                <div style="flex: 1; display: flex; flex-direction: column;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h4 id="selectedGroupName" style="margin: 0; color: var(--primary);">Select a Group</h4>
                        <button id="addUserBtn" class="btn btn-sm btn-success" style="display: none;" onclick="addNewUserRow()">+ Add User</button>
                    </div>
                    <div style="flex: 1; overflow-y: auto;">
                        <table style="width: 100%; text-align: left; border-collapse: collapse;">
                            <thead>
                                <tr style="border-bottom: 1px solid var(--border-color);">
                                    <th style="padding: 8px;">Name</th>
                                    <th style="padding: 8px;">Role</th>
                                    <th style="padding: 8px;">Email</th>
                                    <th style="padding: 8px;">Password</th>
                                    <th style="padding: 8px; width: 60px;">Actions</th>
                                </tr>
                            </thead>
                            <tbody id="userTableBody">
                                <!-- JS populated -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
"""

js_code = """
        // --- Odoo User Management ---
        const listUserBtn = document.getElementById('listUserBtn');
        const userListModal = document.getElementById('userListModal');
        let currentOdooGroups = [];
        let selectedGroupId = null;

        if (listUserBtn) {
            listUserBtn.addEventListener('click', () => {
                document.getElementById('userListFlowName').textContent = `(Flow: ${currentFlowId})`;
                loadOdooUsers();
                userListModal.classList.remove('hidden');
            });
        }

        async function loadOdooUsers() {
            try {
                const res = await fetch(`/api/flows/${currentFlowId}/odoo-users`);
                const data = await res.json();
                currentOdooGroups = data.groups || [];
                
                // Keep selected group if it exists
                if (selectedGroupId && !currentOdooGroups.find(g => g.id === selectedGroupId)) {
                    selectedGroupId = null;
                }
                if (!selectedGroupId && currentOdooGroups.length > 0) {
                    selectedGroupId = currentOdooGroups[0].id;
                }
                
                renderGroups();
                renderUsers();
            } catch (e) {
                console.error("Failed to load Odoo users", e);
            }
        }

        function renderGroups() {
            const list = document.getElementById('userGroupList');
            list.innerHTML = '';
            
            currentOdooGroups.forEach(g => {
                const isSelected = g.id === selectedGroupId;
                const div = document.createElement('div');
                div.style = `padding: 8px; margin-bottom: 4px; border-radius: 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; background: ${isSelected ? 'rgba(99, 102, 241, 0.2)' : 'transparent'}; border: 1px solid ${isSelected ? 'var(--primary)' : 'transparent'};`;
                
                const nameSpan = document.createElement('span');
                nameSpan.textContent = g.name;
                nameSpan.style = isSelected ? 'font-weight: bold; color: var(--text-main);' : 'color: var(--text-muted);';
                
                const delBtn = document.createElement('span');
                delBtn.innerHTML = '🗑️';
                delBtn.style = 'font-size: 12px; opacity: 0.6; cursor: pointer;';
                delBtn.onclick = (e) => {
                    e.stopPropagation();
                    if(confirm(`Delete group '${g.name}'?`)) {
                        deleteGroup(g.id);
                    }
                };
                
                div.appendChild(nameSpan);
                div.appendChild(delBtn);
                
                div.onclick = () => {
                    selectedGroupId = g.id;
                    renderGroups();
                    renderUsers();
                };
                
                list.appendChild(div);
            });
        }

        function renderUsers() {
            const tbody = document.getElementById('userTableBody');
            const groupNameTitle = document.getElementById('selectedGroupName');
            const addUserBtn = document.getElementById('addUserBtn');
            tbody.innerHTML = '';
            
            if (!selectedGroupId) {
                groupNameTitle.textContent = 'Select or Create a Group';
                addUserBtn.style.display = 'none';
                return;
            }
            
            const group = currentOdooGroups.find(g => g.id === selectedGroupId);
            groupNameTitle.textContent = group.name;
            addUserBtn.style.display = 'inline-flex';
            
            (group.users || []).forEach((u, idx) => {
                const tr = document.createElement('tr');
                tr.style = 'border-bottom: 1px solid var(--border-color);';
                
                tr.innerHTML = `
                    <td style="padding: 8px;">${u.name}</td>
                    <td style="padding: 8px;">${u.role}</td>
                    <td style="padding: 8px;">${u.email}</td>
                    <td style="padding: 8px; font-family: monospace;">
                        <div style="display: flex; align-items: center; justify-content: space-between; width: 150px; background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 4px;">
                            <span id="pwd-${idx}" style="-webkit-text-security: disc;">${u.password}</span>
                            <span style="cursor: pointer; opacity: 0.6;" onclick="const el = document.getElementById('pwd-${idx}'); el.style.webkitTextSecurity = el.style.webkitTextSecurity === 'none' ? 'disc' : 'none';">👁️</span>
                        </div>
                    </td>
                    <td style="padding: 8px;">
                        <span style="cursor: pointer; margin-right: 8px;" onclick="editUserRow(${idx})">✏️</span>
                        <span style="cursor: pointer; color: var(--danger);" onclick="deleteUser(${idx})">❌</span>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        function openNewGroupForm() {
            document.getElementById('newGroupForm').style.display = 'block';
            document.getElementById('newGroupName').value = '';
            document.getElementById('newGroupName').focus();
        }

        async function submitNewGroup() {
            const name = document.getElementById('newGroupName').value.trim();
            if (!name) return;
            
            try {
                const res = await fetch(`/api/flows/${currentFlowId}/odoo-users/groups`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name })
                });
                if (res.ok) {
                    document.getElementById('newGroupForm').style.display = 'none';
                    loadOdooUsers();
                } else {
                    const err = await res.json();
                    alert(err.error);
                }
            } catch (e) {
                console.error(e);
            }
        }

        async function deleteGroup(groupId) {
            try {
                await fetch(`/api/flows/${currentFlowId}/odoo-users/groups/${groupId}`, { method: 'DELETE' });
                if (selectedGroupId === groupId) selectedGroupId = null;
                loadOdooUsers();
            } catch(e) {
                console.error(e);
            }
        }

        function addNewUserRow() {
            const tbody = document.getElementById('userTableBody');
            const tr = document.createElement('tr');
            tr.style = 'border-bottom: 1px solid var(--border-color); background: rgba(99, 102, 241, 0.1);';
            tr.innerHTML = `
                <td style="padding: 8px;"><input type="text" id="nu-name" placeholder="Name" class="form-control" style="width: 100%;" /></td>
                <td style="padding: 8px;"><input type="text" id="nu-role" placeholder="Role" class="form-control" style="width: 100%;" /></td>
                <td style="padding: 8px;"><input type="email" id="nu-email" placeholder="Email" class="form-control" style="width: 100%;" /></td>
                <td style="padding: 8px;"><input type="text" id="nu-password" placeholder="Password" class="form-control" style="width: 100%;" /></td>
                <td style="padding: 8px;">
                    <span style="cursor: pointer; margin-right: 8px; color: var(--success);" onclick="saveNewUser()">💾</span>
                    <span style="cursor: pointer; color: var(--danger);" onclick="renderUsers()">✕</span>
                </td>
            `;
            // insert at top
            tbody.insertBefore(tr, tbody.firstChild);
        }

        async function saveNewUser() {
            const user = {
                name: document.getElementById('nu-name').value.trim(),
                role: document.getElementById('nu-role').value.trim(),
                email: document.getElementById('nu-email').value.trim(),
                password: document.getElementById('nu-password').value.trim()
            };
            if(!user.name || !user.email) return alert("Name and Email required");
            
            try {
                await fetch(`/api/flows/${currentFlowId}/odoo-users/groups/${selectedGroupId}/users`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(user)
                });
                loadOdooUsers();
            } catch(e) { console.error(e); }
        }

        function editUserRow(idx) {
            const group = currentOdooGroups.find(g => g.id === selectedGroupId);
            const user = group.users[idx];
            const tbody = document.getElementById('userTableBody');
            const tr = tbody.children[idx];
            
            tr.innerHTML = `
                <td style="padding: 8px;"><input type="text" id="eu-name-${idx}" value="${user.name}" class="form-control" style="width: 100%;" /></td>
                <td style="padding: 8px;"><input type="text" id="eu-role-${idx}" value="${user.role}" class="form-control" style="width: 100%;" /></td>
                <td style="padding: 8px;"><input type="email" id="eu-email-${idx}" value="${user.email}" class="form-control" style="width: 100%;" /></td>
                <td style="padding: 8px;"><input type="text" id="eu-password-${idx}" value="${user.password}" class="form-control" style="width: 100%;" /></td>
                <td style="padding: 8px;">
                    <span style="cursor: pointer; margin-right: 8px; color: var(--success);" onclick="saveEditUser(${idx})">💾</span>
                    <span style="cursor: pointer; color: var(--danger);" onclick="renderUsers()">✕</span>
                </td>
            `;
        }

        async function saveEditUser(idx) {
            const user = {
                name: document.getElementById(`eu-name-${idx}`).value.trim(),
                role: document.getElementById(`eu-role-${idx}`).value.trim(),
                email: document.getElementById(`eu-email-${idx}`).value.trim(),
                password: document.getElementById(`eu-password-${idx}`).value.trim()
            };
            try {
                await fetch(`/api/flows/${currentFlowId}/odoo-users/groups/${selectedGroupId}/users/${idx}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(user)
                });
                loadOdooUsers();
            } catch(e) { console.error(e); }
        }

        async function deleteUser(idx) {
            if(!confirm("Delete this user?")) return;
            try {
                await fetch(`/api/flows/${currentFlowId}/odoo-users/groups/${selectedGroupId}/users/${idx}`, {
                    method: 'DELETE'
                });
                loadOdooUsers();
            } catch(e) { console.error(e); }
        }
"""

if 'id="userListModal"' not in content:
    content = content.replace('    <script>', modal_html + '\n    <script>')

if 'const listUserBtn' not in content:
    content = content.replace('        // --- Auth & Flow Management ---', js_code + '\n        // --- Auth & Flow Management ---')

# add form-control css style
css_code = """
        .form-control {
            padding: 6px;
            border-radius: 4px;
            border: 1px solid var(--border-color);
            background: rgba(0,0,0,0.3);
            color: white;
            font-family: inherit;
            font-size: 13px;
        }
"""
if ".form-control" not in content:
    content = content.replace('</style>', css_code + '</style>')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
