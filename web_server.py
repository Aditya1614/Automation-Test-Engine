import asyncio
import json
import re
import os
import sys
import io
import contextlib
import traceback
import shutil
from fastapi import FastAPI, Request, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from core.excel_parser import TestCaseParser
from core.step_planner_agent import StepPlannerAgent
from core.test_executor import TestExecutor
from core.flow_manager import FlowManager

app = FastAPI(title="SIT Test Automation Web Runner")

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key="sit_super_secret_key")

app.mount("/test-results", StaticFiles(directory="test-results"), name="test-results")
templates = Jinja2Templates(directory="templates")

class AsyncLogStream(io.StringIO):
    def __init__(self, queue: asyncio.Queue):
        super().__init__()
        self.queue = queue

    def write(self, s):
        if s.strip():
            # Fire and forget put_nowait
            self.queue.put_nowait(s.strip())
        return super().write(s)

# --- Data Migration and Setup ---
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
FLOWS_FILE = os.path.join(DATA_DIR, "flows.json")

def initialize_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump([{"username": "admin", "password": "admin123", "display_name": "Admin"}], f)
            
    if not os.path.exists(FLOWS_FILE):
        with open(FLOWS_FILE, "w") as f:
            json.dump([{"id": "other", "name": "Other", "created_by": "system"}], f)
            
    other_flow_dir = os.path.join(DATA_DIR, "flows", "other")
    os.makedirs(other_flow_dir, exist_ok=True)
    
    # Migrate old test_cases.json
    if os.path.exists("test_cases.json"):
        try:
            shutil.move("test_cases.json", os.path.join(other_flow_dir, "test_cases.json"))
        except Exception:
            pass
        
    # Migrate old history.json
    if os.path.exists("test-results/history.json"):
        try:
            shutil.move("test-results/history.json", os.path.join(other_flow_dir, "history.json"))
        except Exception:
            pass
        
    # Migrate old saved_flows
    if os.path.exists("saved_flows") and os.path.isdir("saved_flows"):
        dest_saved_flows = os.path.join(other_flow_dir, "saved_flows")
        os.makedirs(dest_saved_flows, exist_ok=True)
        for item in os.listdir("saved_flows"):
            s = os.path.join("saved_flows", item)
            d = os.path.join(dest_saved_flows, item)
            if not os.path.exists(d):
                try:
                    shutil.move(s, d)
                except Exception:
                    pass


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

# --- Auth Dependencies ---
def get_current_user(request: Request):
    user = request.session.get("username")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not request.session.get("username"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/api/login")
async def login(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
    except Exception:
        users = []
        
    user = next((u for u in users if u["username"] == username and u["password"] == password), None)
    if user:
        request.session["username"] = user["username"]
        request.session["display_name"] = user.get("display_name", username)
        return {"status": "success"}
    else:
        return JSONResponse(status_code=401, content={"error": "Invalid credentials"})

@app.post("/api/logout")
async def logout(request: Request):
    request.session.clear()
    return {"status": "success"}

@app.get("/api/me")
async def get_me(request: Request):
    username = request.session.get("username")
    display_name = request.session.get("display_name")
    if username:
        return {"username": username, "display_name": display_name}
    raise HTTPException(status_code=401, detail="Not authenticated")

# --- Flows API ---
@app.get("/select-flow", response_class=HTMLResponse)
async def select_flow_page(request: Request):
    if not request.session.get("username"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("select_flow.html", {"request": request})

@app.get("/api/flows")
async def get_flows(user: str = Depends(get_current_user)):
    try:
        with open(FLOWS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

@app.get("/api/flows/summary")
async def get_flows_summary(user: str = Depends(get_current_user)):
    try:
        with open(FLOWS_FILE, "r") as f:
            flows = json.load(f)
        
        # Augment with test case counts
        for flow in flows:
            tc_path = os.path.join(DATA_DIR, "flows", flow["id"], "test_cases.json")
            if os.path.exists(tc_path):
                with open(tc_path, "r", encoding="utf-8") as tf:
                    tcs = json.load(tf)
                    flow["test_case_count"] = len(tcs)
            else:
                flow["test_case_count"] = 0
                
        return flows
    except Exception as e:
        return []

@app.post("/api/flows")
async def create_flow(request: Request, user: str = Depends(get_current_user)):
    data = await request.json()
    name = data.get("name")
    if not name:
        return JSONResponse(status_code=400, content={"error": "Name required"})
        
    flow_id = "".join([c.lower() for c in name if c.isalnum() or c == ' ']).replace(" ", "-")
    
    try:
        with open(FLOWS_FILE, "r") as f:
            flows = json.load(f)
    except Exception:
        flows = []
        
    if any(f["id"] == flow_id for f in flows):
        return JSONResponse(status_code=400, content={"error": "Flow already exists"})
        
    flows.append({"id": flow_id, "name": name, "created_by": user})
    
    with open(FLOWS_FILE, "w") as f:
        json.dump(flows, f, indent=4)
        
    # Create directory structure
    flow_dir = os.path.join(DATA_DIR, "flows", flow_id)
    os.makedirs(flow_dir, exist_ok=True)
    os.makedirs(os.path.join(flow_dir, "saved_flows"), exist_ok=True)
    with open(os.path.join(flow_dir, "test_cases.json"), "w") as f:
        json.dump([], f)
    with open(os.path.join(flow_dir, "history.json"), "w") as f:
        json.dump([], f)
    with open(os.path.join(flow_dir, "odoo_users.json"), "w") as f:
        json.dump({"groups": []}, f)
        
    return {"status": "success", "flow": {"id": flow_id, "name": name, "created_by": user}}

# --- Helpers ---
def get_flow_paths(flow_id: str):
    base_dir = os.path.join(DATA_DIR, "flows", flow_id)
    return {
        "test_cases": os.path.join(base_dir, "test_cases.json"),
        "history": os.path.join(base_dir, "history.json"),
        "saved_flows_dir": os.path.join(base_dir, "saved_flows")
    }

def load_test_cases(flow_id: str):
    paths = get_flow_paths(flow_id)
    if os.path.exists(paths["test_cases"]):
        try:
            with open(paths["test_cases"], 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_test_cases(flow_id: str, test_cases: list):
    paths = get_flow_paths(flow_id)
    os.makedirs(os.path.dirname(paths["test_cases"]), exist_ok=True)
    with open(paths["test_cases"], 'w', encoding='utf-8') as f:
        json.dump(test_cases, f, indent=4)

# --- Feature APIs (Scoped by flow_id) ---
@app.get("/api/flows/{flow_id}/test-cases")
async def get_test_cases(flow_id: str, user: str = Depends(get_current_user)):
    return load_test_cases(flow_id)

@app.post("/api/flows/{flow_id}/upload-excel")
async def upload_excel(flow_id: str, file: UploadFile = File(...), user: str = Depends(get_current_user)):
    try:
        contents = await file.read()
        parser = TestCaseParser()
        new_test_cases = parser.parse_from_bytes(contents)
        
        existing_cases = load_test_cases(flow_id)
        existing_ids = {tc.get('id') for tc in existing_cases}
        
        conflicts = []
        for tc in new_test_cases:
            if tc.get('id') in existing_ids:
                conflicts.append(tc.get('id'))
                
        return {
            "all_parsed": new_test_cases,
            "conflicts": conflicts
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/flows/{flow_id}/test-cases/merge")
async def merge_test_cases(flow_id: str, request: Request, user: str = Depends(get_current_user)):
    from datetime import datetime
    data = await request.json()
    new_cases = data.get("test_cases", [])
    overwrite_ids = set(data.get("overwrite_ids", []))
    
    existing_cases = load_test_cases(flow_id)
    existing_map = {tc.get('id'): tc for tc in existing_cases}
    
    current_time = datetime.now().strftime("%d %b %Y, %H:%M:%S")
    
    for tc in new_cases:
        tc_id = tc.get('id')
        
        # New audit trail entry for this upload
        audit_entry = {
            "user": user,
            "date": current_time,
            "action": "overwritten" if tc_id in existing_map else "created"
        }
        
        if tc_id in existing_map:
            if tc_id in overwrite_ids:
                # Merge old upload history if it exists
                old_history = existing_map[tc_id].get("upload_history", [])
                tc["upload_history"] = old_history + [audit_entry]
                tc["uploaded_by"] = user
                tc["uploaded_at"] = current_time
                existing_map[tc_id] = tc
        else:
            tc["upload_history"] = [audit_entry]
            tc["uploaded_by"] = user
            tc["uploaded_at"] = current_time
            existing_map[tc_id] = tc
            
    final_cases = list(existing_map.values())
    save_test_cases(flow_id, final_cases)
    return {"status": "success", "test_cases": final_cases}


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

@app.post("/api/flows/{flow_id}/run")

async def run_test(flow_id: str, request: Request, user: str = Depends(get_current_user)):
    payload = await request.json()
    test_case = payload.get("test_case") if "test_case" in payload else payload
    mode = payload.get("mode", "ai")
    
    paths = get_flow_paths(flow_id)
    flow_manager = FlowManager(saved_flows_dir=paths["saved_flows_dir"])
    
    try:
        odoo_email, odoo_password = resolve_odoo_credentials(flow_id, test_case)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    
    async def event_generator():
        queue = asyncio.Queue()
        log_stream = AsyncLogStream(queue)
        
        async def execute_task():
            try:
                with contextlib.redirect_stdout(log_stream):
                    print(f"--- Running Test Case: {test_case.get('id', 'Unknown')} in {mode.upper()} mode ---")
                    
                    saved_flow = None
                    if mode == "replay":
                        saved_flow = flow_manager.load_flow(test_case.get("id"))
                        if saved_flow:
                            test_case['steps'] = saved_flow.get("planned_steps", [])
                        else:
                            print("ERROR: No saved flow found.")
                            queue.put_nowait({"type": "done", "status": "ERROR", "report_path": None, "recorded_actions": []})
                            return
                    else:
                        print(f"--- Planning Steps for Test Case: {test_case.get('id', 'Unknown')} ---")
                        planner = StepPlannerAgent()
                        planned_steps = await planner.plan_steps(test_case)
                        print("Planned Steps:")
                        print(json.dumps(planned_steps, indent=2))
                        test_case['steps'] = planned_steps
                        
                    executor = TestExecutor(odoo_email, odoo_password)
                    # PASS history_file here!
                    result = await executor.execute(test_case, mode=mode, saved_flow=saved_flow, history_file=paths["history"])
                    
                    queue.put_nowait({
                        "type": "done",
                        "status": result.get("status"),
                        "report_path": result.get("report_path"),
                        "recorded_actions": result.get("recorded_actions", []),
                        "planned_steps": test_case.get("steps", [])
                    })
            except Exception as e:
                traceback.print_exc(file=log_stream)
                queue.put_nowait({"type": "done", "status": "ERROR", "report_path": None, "recorded_actions": [], "planned_steps": []})
                
        task = asyncio.create_task(execute_task())
        
        while True:
            if task.done() and queue.empty(): break
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.5)
                if isinstance(msg, dict) and msg.get("type") == "done":
                    yield f"data: {json.dumps(msg)}\n\n"
                    break
                else:
                    yield f"data: {json.dumps({'type': 'log', 'message': str(msg)})}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/flows/{flow_id}/save-flow")
async def save_flow(flow_id: str, request: Request, user: str = Depends(get_current_user)):
    data = await request.json()
    paths = get_flow_paths(flow_id)
    flow_manager = FlowManager(saved_flows_dir=paths["saved_flows_dir"])
    try:
        flow_manager.save_flow(
            data.get("test_case_id"),
            data.get("planned_steps", []),
            data.get("recorded_actions", [])
        )
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/flows/{flow_id}/saved-flows")
async def get_saved_flows(flow_id: str, user: str = Depends(get_current_user)):
    paths = get_flow_paths(flow_id)
    flow_manager = FlowManager(saved_flows_dir=paths["saved_flows_dir"])
    return flow_manager.list_flows()

@app.delete("/api/flows/{flow_id}/saved-flow/{test_case_id}")
async def delete_saved_flow(flow_id: str, test_case_id: str, user: str = Depends(get_current_user)):
    paths = get_flow_paths(flow_id)
    flow_manager = FlowManager(saved_flows_dir=paths["saved_flows_dir"])
    success = flow_manager.delete_flow(test_case_id)
    return {"status": "success" if success else "failed"}

@app.get("/api/flows/{flow_id}/history")
async def get_history(flow_id: str, user: str = Depends(get_current_user)):
    paths = get_flow_paths(flow_id)
    history_file = paths["history"]
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

@app.delete("/api/flows/{flow_id}/history/{index}")
async def delete_history_entry(flow_id: str, index: int, user: str = Depends(get_current_user)):
    paths = get_flow_paths(flow_id)
    history_file = paths["history"]
    try:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)
            
            if 0 <= index < len(history_data):
                del history_data[index]
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(history_data, f, indent=4)
                return {"status": "success"}
            else:
                return {"error": "Invalid index"}
        return {"error": "History file not found"}
    except Exception as e:
        return {"error": str(e)}

@app.delete("/api/flows/{flow_id}/history/clear")
async def clear_history(flow_id: str, user: str = Depends(get_current_user)):
    paths = get_flow_paths(flow_id)
    history_file = paths["history"]
    try:
        if os.path.exists(history_file):
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump([], f)
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
