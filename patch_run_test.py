import os
import re

file_path = r'c:\DWH\Playwright\web_server.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

credential_resolver_code = """
def resolve_all_odoo_credentials(flow_id: str, test_case: dict) -> list[dict]:
    users_data = load_odoo_users(flow_id)
    
    user_lookup = {}
    for group in users_data.get("groups", []):
        for u in group.get("users", []):
            name = u.get("name", "")
            if name:
                user_lookup[name.lower()] = {
                    "name": name,
                    "email": u.get("email"),
                    "password": u.get("password")
                }
                
    test_step_detail = test_case.get("test_step_detail", "")
    cleaned = re.sub(r'(Login sebagai\s*:\s*)+', 'Login sebagai: ', test_step_detail, flags=re.IGNORECASE)
    matches = re.findall(r'Login sebagai\s*:\s*(.+)', cleaned, re.IGNORECASE)
    
    if matches:
        credentials_list = []
        seen = set()
        for raw_name in matches:
            name = raw_name.strip()
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            
            if name.lower() in user_lookup:
                credentials_list.append(user_lookup[name.lower()])
            else:
                for key, cred in user_lookup.items():
                    if key in name.lower() or name.lower() in key:
                        credentials_list.append(cred)
                        break
                        
        if credentials_list:
            return credentials_list
            
    search_text = (test_case.get("pre_conditions", "") + " " + test_case.get("test_data", "") + " " + test_case.get("test_step_detail", "")).lower()
    search_text_no_space = re.sub(r'\s+', '', search_text)
    
    for group in users_data.get("groups", []):
        for u in group.get("users", []):
            name = u.get("name", "").lower()
            if name and name in search_text:
                return [{"name": u["name"], "email": u["email"], "password": u["password"]}]
            
            name_no_space = re.sub(r'\s+', '', name)
            if name_no_space and name_no_space in search_text_no_space:
                return [{"name": u["name"], "email": u["email"], "password": u["password"]}]
                
    test_data = test_case.get("test_data", "")
    email_match = re.search(r'Email:\s*([^\s\n]+)', test_data, re.IGNORECASE)
    pass_match = re.search(r'Password:\s*([^\s\n]+)', test_data, re.IGNORECASE)
    
    if email_match and pass_match:
        return [{"name": "inline", "email": email_match.group(1), "password": pass_match.group(1)}]
        
    raise ValueError("No Odoo credentials found for this test case. Please check pre_conditions, test_data, or test_step_detail, or add the user to the User List.")

"""

run_test_patch = """
    try:
        credentials = resolve_all_odoo_credentials(flow_id, test_case)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
        
    async def event_generator():
        queue = asyncio.Queue()
        log_stream = AsyncLogStream(queue)
        
        try:
            executor = TestExecutor(credentials)
            executor.pw.logger = log_stream
            
"""

if "def resolve_all_odoo_credentials" not in content:
    content = content.replace('@app.post("/api/flows/{flow_id}/run")', credential_resolver_code + '@app.post("/api/flows/{flow_id}/run")')

if "credentials = resolve_all_odoo_credentials" not in content:
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

