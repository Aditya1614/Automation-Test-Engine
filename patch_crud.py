import os

file_path = r'c:\DWH\Playwright\web_server.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

crud_code = """
# --- Odoo Users CRUD API ---
def get_odoo_users_path(flow_id: str):
    return os.path.join(DATA_DIR, "flows", flow_id, "odoo_users.json")

def load_odoo_users(flow_id: str):
    path = get_odoo_users_path(flow_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"groups": []}

def save_odoo_users(flow_id: str, data: dict):
    path = get_odoo_users_path(flow_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

@app.get("/api/flows/{flow_id}/odoo-users")
async def get_odoo_users_api(flow_id: str, user: str = Depends(get_current_user)):
    return load_odoo_users(flow_id)

@app.post("/api/flows/{flow_id}/odoo-users/groups")
async def create_odoo_user_group(flow_id: str, request: Request, user: str = Depends(get_current_user)):
    data = await request.json()
    name = data.get("name")
    if not name:
        return JSONResponse(status_code=400, content={"error": "Group name is required"})
    
    users_data = load_odoo_users(flow_id)
    group_id = "".join([c.lower() for c in name if c.isalnum() or c == ' ']).replace(" ", "-")
    
    if any(g.get("id") == group_id for g in users_data.get("groups", [])):
        return JSONResponse(status_code=400, content={"error": "Group already exists"})
        
    users_data.setdefault("groups", []).append({
        "id": group_id,
        "name": name,
        "users": []
    })
    
    save_odoo_users(flow_id, users_data)
    return {"status": "success", "groups": users_data["groups"]}

@app.delete("/api/flows/{flow_id}/odoo-users/groups/{group_id}")
async def delete_odoo_user_group(flow_id: str, group_id: str, user: str = Depends(get_current_user)):
    users_data = load_odoo_users(flow_id)
    users_data["groups"] = [g for g in users_data.get("groups", []) if g.get("id") != group_id]
    save_odoo_users(flow_id, users_data)
    return {"status": "success"}

@app.post("/api/flows/{flow_id}/odoo-users/groups/{group_id}/users")
async def add_odoo_user(flow_id: str, group_id: str, request: Request, user: str = Depends(get_current_user)):
    data = await request.json()
    users_data = load_odoo_users(flow_id)
    
    group = next((g for g in users_data.get("groups", []) if g.get("id") == group_id), None)
    if not group:
        return JSONResponse(status_code=404, content={"error": "Group not found"})
        
    group.setdefault("users", []).append({
        "name": data.get("name", ""),
        "role": data.get("role", ""),
        "email": data.get("email", ""),
        "password": data.get("password", "")
    })
    
    save_odoo_users(flow_id, users_data)
    return {"status": "success", "groups": users_data["groups"]}

@app.put("/api/flows/{flow_id}/odoo-users/groups/{group_id}/users/{user_index}")
async def edit_odoo_user(flow_id: str, group_id: str, user_index: int, request: Request, user: str = Depends(get_current_user)):
    data = await request.json()
    users_data = load_odoo_users(flow_id)
    
    group = next((g for g in users_data.get("groups", []) if g.get("id") == group_id), None)
    if not group:
        return JSONResponse(status_code=404, content={"error": "Group not found"})
        
    if 0 <= user_index < len(group.get("users", [])):
        group["users"][user_index] = {
            "name": data.get("name", ""),
            "role": data.get("role", ""),
            "email": data.get("email", ""),
            "password": data.get("password", "")
        }
        save_odoo_users(flow_id, users_data)
        return {"status": "success", "groups": users_data["groups"]}
    return JSONResponse(status_code=404, content={"error": "User not found"})

@app.delete("/api/flows/{flow_id}/odoo-users/groups/{group_id}/users/{user_index}")
async def delete_odoo_user(flow_id: str, group_id: str, user_index: int, user: str = Depends(get_current_user)):
    users_data = load_odoo_users(flow_id)
    
    group = next((g for g in users_data.get("groups", []) if g.get("id") == group_id), None)
    if not group:
        return JSONResponse(status_code=404, content={"error": "Group not found"})
        
    if 0 <= user_index < len(group.get("users", [])):
        group["users"].pop(user_index)
        save_odoo_users(flow_id, users_data)
        return {"status": "success", "groups": users_data["groups"]}
    return JSONResponse(status_code=404, content={"error": "User not found"})

@app.post("/api/flows/{flow_id}/run")
"""

if "def load_odoo_users" not in content:
    content = content.replace('@app.post("/api/flows/{flow_id}/run")', crud_code)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
