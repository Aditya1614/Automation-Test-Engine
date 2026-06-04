import os
import re

file_path = r'c:\DWH\Playwright\web_server.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

credential_resolver_code = """
def resolve_odoo_credentials(flow_id: str, test_case: dict) -> tuple[str, str]:
    users_data = load_odoo_users(flow_id)
    
    # 1. Check for user name in test_case
    search_text = (test_case.get("pre_conditions", "") + " " + test_case.get("test_data", "")).lower()
    
    for group in users_data.get("groups", []):
        for u in group.get("users", []):
            name = u.get("name", "").lower()
            if name and name in search_text:
                return u.get("email"), u.get("password")
                
    # 2. Check for inline Email: / Password:
    test_data = test_case.get("test_data", "")
    email_match = re.search(r'Email:\s*([^\s\n]+)', test_data, re.IGNORECASE)
    pass_match = re.search(r'Password:\s*([^\s\n]+)', test_data, re.IGNORECASE)
    
    if email_match and pass_match:
        return email_match.group(1), pass_match.group(1)
        
    raise ValueError("No Odoo credentials found for this test case. Please check pre_conditions or test_data, or add the user to the User List.")

"""

run_test_patch = """
    try:
        odoo_email, odoo_password = resolve_odoo_credentials(flow_id, test_case)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
        
    async def event_generator():
        queue = asyncio.Queue()
        log_stream = AsyncLogStream(queue)
        
        try:
            executor = TestExecutor(odoo_email, odoo_password)
            executor.pw.logger = log_stream
            
"""

if "def resolve_odoo_credentials" not in content:
    content = content.replace('@app.post("/api/flows/{flow_id}/run")', credential_resolver_code + '@app.post("/api/flows/{flow_id}/run")')

if "odoo_email, odoo_password = resolve_odoo_credentials" not in content:
    # We replace the inside of run_test
    target_str = """    async def event_generator():
        queue = asyncio.Queue()
        log_stream = AsyncLogStream(queue)
        
        try:
            executor = TestExecutor()
            executor.pw.logger = log_stream"""
    content = content.replace(target_str, run_test_patch.strip())

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
