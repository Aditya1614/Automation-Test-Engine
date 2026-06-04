import os
import sys

file_path = r'c:\DWH\Playwright\web_server.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Patch initialize_data
initialize_patch = """
    # Seed odoo_users.json for all flows
    odoo_email = os.getenv("ODOO_EMAIL", "admin@example.com")
    odoo_password = os.getenv("ODOO_PASSWORD", "admin")
    flows_dir = os.path.join(DATA_DIR, "flows")
    if os.path.exists(flows_dir):
        for flow_id in os.listdir(flows_dir):
            flow_path = os.path.join(flows_dir, flow_id)
            if os.path.isdir(flow_path):
                users_path = os.path.join(flow_path, "odoo_users.json")
                if not os.path.exists(users_path):
                    with open(users_path, "w") as f:
                        json.dump({
                            "groups": [
                                {
                                    "id": "default",
                                    "name": "Default Group",
                                    "users": [
                                        {
                                            "name": "Admin (from .env)",
                                            "role": "Administrator",
                                            "email": odoo_email,
                                            "password": odoo_password
                                        }
                                    ]
                                }
                            ]
                        }, f, indent=4)

initialize_data()
"""
if "# Seed odoo_users.json for all flows" not in content:
    content = content.replace("initialize_data()\n", initialize_patch)

# Patch create_flow
create_flow_patch = """    with open(os.path.join(flow_dir, "history.json"), "w") as f:
        json.dump([], f)
    with open(os.path.join(flow_dir, "odoo_users.json"), "w") as f:
        json.dump({"groups": []}, f)
"""
if "odoo_users.json" not in content.split('def create_flow')[1]:
    content = content.replace('    with open(os.path.join(flow_dir, "history.json"), "w") as f:\n        json.dump([], f)\n', create_flow_patch)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
