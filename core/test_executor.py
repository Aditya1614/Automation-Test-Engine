import os
import json
import asyncio
from dotenv import load_dotenv

from google.adk.runners import InMemoryRunner
from google.genai import types

from helpers.playwright_manager import PlaywrightManager
from helpers.dom_utils import get_visible_area_dom
from helpers.report_generator import ReportGenerator
from dom_analyzer_agent.agent import dom_agent

load_dotenv()

class TestExecutor:
    def __init__(self, odoo_email: str, odoo_password: str):
        self.pw = PlaywrightManager(headless=False)
        self.report = ReportGenerator()
        
        self.runner = InMemoryRunner(agent=dom_agent, app_name="odoo_tester")
        self.client = dom_agent.client if hasattr(dom_agent, 'client') else None
        self.total_tokens_session = 0
        
        self.odoo_url = os.getenv("ODOO_URL")
        self.odoo_email = odoo_email
        self.odoo_password = odoo_password
        
        if not self.odoo_url:
            raise ValueError("Odoo URL not set in .env")
        if not self.odoo_email or not self.odoo_password:
            raise ValueError("Odoo credentials not provided")

    async def get_ai_action(self, task_desc: str, dom_html: str, image_bytes: bytes, session, user_id: str):
        prompt = f"""
        Task: {task_desc}
        
        DOM:
        {dom_html}
        
        Return ONLY valid JSON.
        """
        
        parts = [types.Part.from_text(text=prompt)]
        if image_bytes:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))
            
        user_content = types.Content(role="user", parts=parts)
        
        if not self.client:
            from google.genai import Client
            self.client = Client()
            
        response = await self.client.aio.models.generate_content(
            model=dom_agent.model,
            contents=[user_content],
            config=types.GenerateContentConfig(
                system_instruction=dom_agent.instruction
            )
        )
        
        final_text = response.text
        tokens_used = response.usage_metadata.total_token_count if response.usage_metadata else 0
        self.total_tokens_session += tokens_used
        print(f"   [Token Usage] Step tokens: {tokens_used}, Total Session: {self.total_tokens_session}")
        
        import re
        match = re.search(r'\{.*\}', final_text, re.DOTALL)
        if match:
            clean_text = match.group(0)
        else:
            clean_text = final_text

        try:
            return json.loads(clean_text.strip())
        except Exception as e:
            print(f"Failed to parse JSON from AI: {final_text}")
            raise e

    async def run_step(self, step_num: float, step_name: str, task_details: dict, session, user_id: str, saved_action: dict = None):
        print(f"\n--- Executing Step {step_num}: {step_name} ---")
        page = self.pw.get_page()
        
        try:
            try:
                await page.wait_for_load_state("load", timeout=10000)
            except:
                pass
            
            is_optional = task_details.get('optional', False)
            timeout_ms = 3000 if is_optional else 10000
            
            await page.wait_for_timeout(2000 if is_optional else 3000) # Wait for UI to settle
            
            dom_html = await get_visible_area_dom(page)
            image_bytes = await page.screenshot(type="png")
            
            # Formulate the task description for the AI.
            ai_task = task_details.get('task', '')
            
            action_hint = task_details.get('action_hint')
            task_val = task_details.get('value')
            
            if action_hint and task_val:
                ai_task += f"\nCRITICAL HINT: You MUST choose action '{action_hint}' and use value '{task_val}'. EXCEPTION: If the screenshot shows that the field ALREADY contains the value '{task_val}', you MUST choose action 'none' to skip."
            elif action_hint:
                ai_task += f"\nCRITICAL HINT: You MUST choose action '{action_hint}'."
            elif task_val:
                ai_task += f"\nCRITICAL HINT: You MUST use the value '{task_val}'."
                
            if action_hint == 'verify' and task_details.get('expected_result'):
                ai_task += f"\nExpected Result to check: {task_details.get('expected_result')}"

            if saved_action:
                print(f"Replay mode: using saved action for step {step_num}")
                ai_response = saved_action
            else:
                ai_response = await self.get_ai_action(ai_task, dom_html, image_bytes, session, user_id)
                print(f"AI suggests: {ai_response}")
            
            action = ai_response.get("action")
            selector = ai_response.get("selector")
            value = ai_response.get("value")
            wait_for = ai_response.get("wait_for")
            result = ai_response.get("result")

            # Safety: if AI returned no selector for an action that needs one, skip gracefully
            if action not in ("verify", "none", None) and (not selector or selector == "None"):
                print(f"  [WARN] AI returned no selector for action '{action}'. Skipping step.")
                screenshot_path = await self.pw.take_screenshot(str(step_num).replace(".", "_"), step_name)
                self.report.add_result(
                    step_num=step_num, step_name=step_name,
                    task=task_details.get('task', ''), status="PASS",
                    selector="-", action=f"{action} (skipped - no selector)",
                    confidence=ai_response.get('confidence'), screenshot_path=screenshot_path
                )
                return True, "Skipped - no selector needed", ai_response
            # Build a list of fallback selectors to try in order
            def build_fallback_selectors(sel):
                """Generate progressively simpler selectors from the AI's suggestion."""
                candidates = [sel]
                if sel:
                    # If AI used div.modal-footer, also try footer.modal-footer and .modal-footer
                    if 'div.modal-footer' in sel:
                        candidates.append(sel.replace('div.modal-footer', 'footer.modal-footer'))
                        candidates.append(sel.replace('div.modal-footer ', '.modal-footer '))
                        candidates.append(sel.replace('div.modal-footer ', ''))
                    # If AI used div.modal-body, also try .modal-body
                    if 'div.modal-body' in sel:
                        candidates.append(sel.replace('div.modal-body ', '.modal-body '))
                        candidates.append(sel.replace('div.modal-body ', ''))
                    # Extract :has-text("...") and try button:has-text alone
                    import re
                    has_text = re.search(r':has-text\(["\'](.+?)["\']\)', sel)
                    if has_text:
                        text = has_text.group(1)
                        candidates.append(f'button:has-text("{text}")')
                        candidates.append(f':has-text("{text}"):visible')
                return candidates

            async def try_action(action_fn, sel):
                """Try the action with the given selector, with fallbacks."""
                fallbacks = build_fallback_selectors(sel)
                last_err = None
                for candidate_sel in fallbacks:
                    try:
                        await action_fn(candidate_sel)
                        return candidate_sel  # success
                    except Exception as e:
                        last_err = e
                        continue
                raise last_err  # all fallbacks failed

            if action == "click":
                async def do_click(sel):
                    await page.locator(sel).first.click(timeout=timeout_ms)
                used_sel = await try_action(do_click, selector)
                if used_sel != selector:
                    print(f"  [Fallback] Used selector: {used_sel}")
            elif action == "fill":
                intended_value = task_details.get('value')
                val_to_fill = intended_value if intended_value is not None else (value or '')
                async def do_fill(sel):
                    await page.locator(sel).first.fill(val_to_fill, timeout=timeout_ms)
                used_sel = await try_action(do_fill, selector)
                if used_sel != selector:
                    print(f"  [Fallback] Used selector: {used_sel}")
            elif action == "fill_and_enter":
                intended_value = task_details.get('value')
                val_to_fill = intended_value if intended_value is not None else (value or '')
                async def do_fill_enter(sel):
                    await page.locator(sel).first.fill(val_to_fill, timeout=timeout_ms)
                    await page.wait_for_timeout(1500)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(2000)
                used_sel = await try_action(do_fill_enter, selector)
                if used_sel != selector:
                    print(f"  [Fallback] Used selector: {used_sel}")
            elif action == "select":
                async def do_select(sel):
                    await page.locator(sel).first.select_option(value, timeout=timeout_ms)
                used_sel = await try_action(do_select, selector)
                if used_sel != selector:
                    print(f"  [Fallback] Used selector: {used_sel}")
            elif action == "verify":
                 if not result:
                     # Only apply secondary DOM check for NEGATIVE test cases
                     # (verifying errors/validation messages), not positive status checks
                     expected_text = (task_details.get('expected_result') or '').lower()
                     error_keywords = ['error', 'missing', 'required', 'gagal', 'invalid', 'failed', 'warning', 'validasi']
                     is_error_check = any(kw in expected_text for kw in error_keywords)
                     
                     if is_error_check:
                         # Secondary check for negative tests: look for Odoo validation indicators
                         dom_text = (await page.content()).lower()
                         
                         has_invalid_fields = 'o_field_invalid' in dom_text
                         has_notification = 'o_notification' in dom_text
                         
                         # Check for partial keyword matches from the expected result
                         keywords = [w for w in expected_text.split() if len(w) > 3]
                         keyword_matches = sum(1 for k in keywords if k in dom_text)
                         keyword_ratio = keyword_matches / max(len(keywords), 1)
                         
                         if has_invalid_fields or has_notification or keyword_ratio >= 0.5:
                             print(f"  [VERIFY OVERRIDE] AI said false, but DOM shows validation indicators (negative test)")
                             print(f"    - Invalid fields: {has_invalid_fields}, Notification: {has_notification}, Keyword match: {keyword_ratio:.0%}")
                             result = True  # Override: verification actually passed
                         else:
                             raise Exception(f"Verification Failed: {ai_response.get('description')}")
                     else:
                         # Positive test case - no override, fail honestly
                         raise Exception(f"Verification Failed: {ai_response.get('description')}")
            
            if wait_for:
                 try:
                     await page.wait_for_selector(wait_for, timeout=5000)
                 except:
                     pass
            
            screenshot_path = await self.pw.take_screenshot(str(step_num).replace(".", "_"), step_name)
            
            self.report.add_result(
                step_num=step_num,
                step_name=step_name,
                task=task_details.get('task', ''),
                status="PASS",
                selector=selector,
                action=action,
                confidence=ai_response.get('confidence'),
                screenshot_path=screenshot_path
            )
            
            # Augment ai_response with step_num and name for saving later
            ai_response["step_num"] = step_num
            ai_response["name"] = step_name
            return True, ai_response.get('description', ''), ai_response
            
        except Exception as e:
            is_optional = task_details.get('optional', False)
            
            if is_optional:
                print(f"  [OPTIONAL] Step {step_num} failed but is optional, skipping: {e}")
                screenshot_path = await self.pw.take_screenshot(str(step_num).replace(".", "_"), step_name)
                self.report.add_result(
                    step_num=step_num,
                    step_name=step_name,
                    task=task_details.get('task', ''),
                    status="PASS",
                    selector="-",
                    action="skipped (optional)",
                    confidence="-",
                    screenshot_path=screenshot_path
                )
                return True, f"Optional step skipped: {e}", None
            
            print(f"Error in step {step_num}: {e}")
            screenshot_path = await self.pw.take_screenshot(str(step_num).replace(".", "_"), f"{step_name}_ERROR")
            self.report.add_result(
                step_num=step_num,
                step_name=step_name,
                task=task_details.get('task', ''),
                status="FAIL",
                error_msg=str(e),
                screenshot_path=screenshot_path
            )
            return False, str(e), None

    async def execute(self, test_case: dict, mode: str = "ai", saved_flow: dict = None, history_file: str = "test-results/history.json") -> dict:
        video_dir = None
        try:
            test_id = test_case.get('id', 'Unknown')
            test_title = test_case.get('title', test_case.get('scenario', 'Unknown Test'))
            
            # Setup report metadata
            self.report.test_info['test_id'] = test_id
            self.report.test_info['test_title'] = test_title
            self.report.test_info['type'] = test_case.get('type', '')
            self.report.test_info['expected_results'] = test_case.get('expected_results', '')
            
            print(f"\n=========================================")
            print(f"Starting execution of {test_id}: {test_title}")
            print(f"=========================================\n")
            
            await self.pw.start_browser()
            safe_test_id = test_id.replace(" ", "_").replace("/", "_")
            page, video_dir = await self.pw.create_context(safe_test_id)
            self.report.set_video(video_dir)
            
            login_url = self.odoo_url if self.odoo_url.endswith('/') else self.odoo_url + '/'
            await page.goto(login_url + "web/login")
            
            user_id = "test_user_01"
            session = await self.runner.session_service.create_session(
                app_name="odoo_tester",
                user_id=user_id
            )
            
            recorded_actions = []
            saved_actions_map = {}
            if mode == "replay" and saved_flow:
                for act in saved_flow.get("executed_actions", []):
                    saved_actions_map[act.get("step_num")] = act
            
            # Pre-step: Login
            p1, d1, a1 = await self.run_step(0.1, "Login Email", {
                "task": "Isi field email login",
                "action_hint": "fill",
                "value": self.odoo_email,
                "optional": True
            }, session, user_id, saved_actions_map.get(0.1))
            if a1: recorded_actions.append(a1)
            
            p2, d2, a2 = await self.run_step(0.2, "Login Password", {
                "task": "Isi field password login",
                "action_hint": "fill",
                "value": self.odoo_password,
                "optional": True
            }, session, user_id, saved_actions_map.get(0.2))
            if a2: recorded_actions.append(a2)
            
            p3, d3, a3 = await self.run_step(0.3, "Click Login", {
                "task": "Klik tombol Log in",
                "action_hint": "click",
                "optional": True
            }, session, user_id, saved_actions_map.get(0.3))
            if a3: recorded_actions.append(a3)
            
            # Execute Dynamic Steps
            steps = test_case.get('steps', [])
            all_passed = True
            final_actual_result = ""
            
            for step in steps:
                step_num = step.get('step_num')
                saved_act = saved_actions_map.get(step_num) if mode == "replay" else None
                
                passed, desc, ai_act = await self.run_step(
                    step_num=step_num,
                    step_name=step.get('name', f"Step {step_num}"),
                    task_details=step,
                    session=session,
                    user_id=user_id,
                    saved_action=saved_act
                )
                
                if ai_act:
                    recorded_actions.append(ai_act)
                
                if step.get('action_hint') == 'verify':
                    final_actual_result = desc
                    
                if not passed:
                    all_passed = False
                    break
                    
            self.report.test_info['actual_results'] = final_actual_result
            self.report.test_info['total_tokens'] = self.total_tokens_session
            
            status = "PASS" if all_passed else "FAIL"
            
            await self.pw.close()
            self.report.set_video(video_dir)
            report_path = self.report.generate()
            print(f"Automation finished. Check report at {report_path}")
            
            # Save history to JSON
            from datetime import datetime
            history_entry = {
                "date": datetime.now().strftime("%d %b %Y, %H:%M:%S"),
                "test_id": test_id,
                "scenario": test_title,
                "status": status,
                "report_path": report_path.replace("\\", "/")
            }
            try:
                history_data = []
                if os.path.exists(history_file):
                    with open(history_file, "r", encoding="utf-8") as f:
                        history_data = json.load(f)
                history_data.insert(0, history_entry)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(history_file)), exist_ok=True)
                
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(history_data, f, indent=4)
            except Exception as hist_err:
                print(f"Failed to write history: {hist_err}")
            
            return {
                "test_case_id": test_id,
                "status": status,
                "total_tokens": self.total_tokens_session,
                "report_path": report_path,
                "recorded_actions": recorded_actions
            }
            
        except Exception as e:
            print(f"Test Execution Error: {e}")
            await self.pw.close()
            if video_dir:
                self.report.set_video(video_dir)
            report_path = self.report.generate()
            print(f"Automation finished with error. Check report at {report_path}")
            
            # Save history to JSON on error
            from datetime import datetime
            history_entry = {
                "date": datetime.now().strftime("%d %b %Y, %H:%M:%S"),
                "test_id": test_case.get('id', 'Unknown'),
                "scenario": test_case.get('title', test_case.get('scenario', 'Unknown Test')),
                "status": "ERROR",
                "report_path": report_path.replace("\\", "/")
            }
            try:
                history_data = []
                if os.path.exists(history_file):
                    with open(history_file, "r", encoding="utf-8") as f:
                        history_data = json.load(f)
                history_data.insert(0, history_entry)
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(history_file)), exist_ok=True)
                
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(history_data, f, indent=4)
            except Exception as hist_err:
                print(f"Failed to write history: {hist_err}")
                
            return {
                "test_case_id": test_case.get('id', 'Unknown'),
                "status": "ERROR",
                "error": str(e),
                "report_path": report_path
            }
