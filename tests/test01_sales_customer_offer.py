import os
import json
import asyncio
from dotenv import load_dotenv

# ADK and Gemini imports
from google.adk.runners import InMemoryRunner
from google.genai import types

from helpers.playwright_manager import PlaywrightManager
from helpers.dom_utils import get_visible_area_dom
from helpers.report_generator import ReportGenerator
from dom_analyzer_agent import dom_agent

load_dotenv()

class OdooTestRunner:
    def __init__(self):
        self.pw = PlaywrightManager(headless=False)
        self.report = ReportGenerator()
        
        # Setup ADK Runner for our dom agent
        self.runner = InMemoryRunner(agent=dom_agent, app_name="odoo_tester")
        self.client = dom_agent.client if hasattr(dom_agent, 'client') else None
        self.total_tokens_session = 0
        
        self.odoo_url = os.getenv("ODOO_URL")
        self.odoo_email = os.getenv("ODOO_EMAIL")
        self.odoo_password = os.getenv("ODOO_PASSWORD")
        
        if not self.odoo_url or not self.odoo_email or not self.odoo_password:
            raise ValueError("Odoo credentials not set in .env")

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
        
        # Bypass ADK runner to get straightforward token counts
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

    async def run_step(self, step_num: float, step_name: str, task_details: dict, session, user_id: str):
        print(f"\n--- Executing Step {step_num}: {step_name} ---")
        page = self.pw.get_page()
        
        try:
            # 1. Capture & prune DOM
            try:
                await page.wait_for_load_state("load", timeout=10000)
            except:
                pass # Ignore timeout if page is mostly loaded
            
            # Wait a bit more for Odoo's OWL to settle (Odoo can be slow to render forms)
            await page.wait_for_timeout(5000)
            
            dom_html = await get_visible_area_dom(page)
            # print(f"Captured DOM size: {len(dom_html)} chars")
            
            # 1.5 Capture Screenshot for Multimodal AI
            image_bytes = await page.screenshot(type="png")
            
            # 2. Get action from AI
            ai_response = await self.get_ai_action(task_details['task'], dom_html, image_bytes, session, user_id)
            print(f"AI suggests: {ai_response}")
            
            action = ai_response.get("action")
            selector = ai_response.get("selector")
            value = ai_response.get("value")
            wait_for = ai_response.get("wait_for")
            
            # 3. Execute action
            if action == "click":
                await page.locator(selector).first.click(timeout=10000)
            elif action == "fill":
                # ALWAYS use our intended value if provided, else fallback to AI's value
                intended_value = task_details.get('value')
                val_to_fill = intended_value if intended_value is not None else (value or '')
                await page.locator(selector).first.fill(val_to_fill, timeout=10000)
            elif action == "fill_and_enter":
                intended_value = task_details.get('value')
                val_to_fill = intended_value if intended_value is not None else (value or '')
                await page.locator(selector).first.fill(val_to_fill, timeout=10000)
                await page.wait_for_timeout(1500) # Wait for Odoo dropdown to populate
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2000) # Give Odoo time to process Enter
            elif action == "select":
                 await page.locator(selector).first.select_option(value, timeout=10000)
            
            # Optional explicit wait requested by AI
            if wait_for:
                 try:
                     await page.wait_for_selector(wait_for, timeout=5000)
                 except:
                     pass # Don't fail if wait_for is wrong
            
            # 4. Take Screenshot
            screenshot_path = await self.pw.take_screenshot(str(step_num).replace(".", "_"), step_name)
            
            # Log success
            self.report.add_result(
                step_num=step_num,
                step_name=step_name,
                task=task_details['task'],
                status="PASS",
                selector=selector,
                action=action,
                confidence=ai_response.get('confidence'),
                screenshot_path=screenshot_path
            )
            
        except Exception as e:
            print(f"Error in step {step_num}: {e}")
            screenshot_path = await self.pw.take_screenshot(str(step_num).replace(".", "_"), f"{step_name}_ERROR")
            self.report.add_result(
                step_num=step_num,
                step_name=step_name,
                task=task_details['task'],
                status="FAIL",
                error_msg=str(e),
                screenshot_path=screenshot_path
            )
            raise e # Reraise to stop execution on failure

    async def execute(self):
        try:
            await self.pw.start_browser()
            page, video_dir = await self.pw.create_context("odoo_sales_offer")
            self.report.set_video(video_dir)
            
            # Navigate directly to login page to avoid landing page confusion
            login_url = self.odoo_url if self.odoo_url.endswith('/') else self.odoo_url + '/'
            await page.goto(login_url + "web/login")
            
            # Setup ADK Session
            user_id = "test_user_01"
            session = await self.runner.session_service.create_session(
                app_name="odoo_tester",
                user_id=user_id
            )
            
            # Step 0: Login (We can do this without AI for stability, or with AI. Let's do a mix or hardcode for login as it's standard)
            # But the requirement says use AI. We will try AI.
            await self.run_step(0.1, "Login Email", {
                "task": "Isi field email login",
                "value": self.odoo_email
            }, session, user_id)
            
            await self.run_step(0.2, "Login Password", {
                "task": "Isi field password login",
                "value": self.odoo_password
            }, session, user_id)
            
            await self.run_step(0.3, "Click Login", {
                "task": "Klik tombol Log in"
            }, session, user_id)
            
            # Step 1: Navigasi
            # Odoo 19 uses an app switcher or direct menu
            await self.run_step(1, "Navigate to Sales", {
                "task": "Klik menu 'Sales' di dashboard atau app switcher"
            }, session, user_id)
            
            await self.run_step(1.1, "Click Customer Offers", {
                "task": "Klik submenu 'Customer Offers' di navigation bar atas"
            }, session, user_id)
            
            await self.run_step(1.2, "Click New", {
                "task": "Klik tombol 'New' untuk membuat offer baru"
            }, session, user_id)
            
            # Step 2: Pilih Customer
            await self.run_step(2, "Pilih Customer", {
                "task": "Isi field Customer dengan mengetik nama customer lalu enter. Cari input text untuk field 'partner_id'. Pilih action fill_and_enter.",
                "value": "AGUS SUTIKNO/PBG"
            }, session, user_id)
            
            # Wait for customer data to load
            await page.wait_for_timeout(1000)
            
            # Step 3: Set Tanggal
            from datetime import datetime, timedelta
            valid_date = (datetime.now() + timedelta(days=14)).strftime("%m/%d/%Y")
            await self.run_step(3, "Set Valid Date", {
                "task": "Isi field 'Expiration' atau 'Valid Date' (Hint: field ini biasanya berada di dalam div dengan name='validity_date', cari elemen input text di dalamnya). Pilih action fill_and_enter.",
                "value": valid_date
            }, session, user_id)
            
            # Step 3.1: Set Order Date
            order_date = datetime.now().strftime("%m/%d/%Y")
            await self.run_step(3.1, "Set Order Date", {
                "task": "Isi field 'Order Date' atau 'Quotation Date' (Hint: field ini biasanya berada di dalam div dengan name='date_order', cari elemen input text di dalamnya). Pilih action fill_and_enter.",
                "value": order_date
            }, session, user_id)
            
            # Step 4: Add Line
            await self.run_step(4, "Add a line", {
                "task": "Klik link 'Add a line' di dalam tabel Order Lines. (Hint: tabel order lines ada di dalam div dengan name='order_line')"
            }, session, user_id)
            
            # Wait for wizard/modal
            await page.wait_for_timeout(2000)
            
            # Step 5: Product Detail
            await self.run_step(5, "Pilih Type OSS", {
                "task": "Pilih nilai 'OSS' pada field 'Type' (jika ada). Jika di screenshot nilai 'Type' sudah 'OSS', kembalikan action 'none' saja.",
                "value": "OSS"
            }, session, user_id)
            
            await self.run_step(5.1, "Pilih Product", {
                "task": "Isi field Product (Hint: field Product biasanya berada di dalam div dengan name='product_template_id' atau 'product_id', cari elemen input text di dalamnya) lalu enter. Pilih action fill_and_enter.",
                "value": "[25555] PortoLady GLM-8 size 36-40 @48"
            }, session, user_id)
            
            # Step 6: Qty & Save
            await self.run_step(6, "Isi Qty", {
                "task": "Isi field Quantity (cari input untuk field 'product_uom_qty' atau 'quantity') dengan angka 10",
                "value": "10"
            }, session, user_id)
            
            await self.run_step(6.1, "Save & Close", {
                "task": "Klik tombol 'Save & Close' pada modal/wizard"
            }, session, user_id)
            
            # Wait for line to be added and modal overlay to disappear completely
            await page.wait_for_timeout(2000)
            # Odoo's modal backdrop blocks clicks if it doesn't close (e.g. validation error)
            # We want this to fail loudly if the modal refuses to close!
            await page.wait_for_selector(".modal", state="hidden", timeout=10000)
            
            # Step 7: Confirm
            await self.run_step(7, "Confirm", {
                "task": "Klik tombol 'Confirm' di header form"
            }, session, user_id)
            
            # Wait for status change
            await page.wait_for_timeout(2000)
            
            # Step 8: Mark as Done
            await self.run_step(8, "Mark as Done", {
                "task": "Klik tombol 'Mark as Done'"
            }, session, user_id)
            
        except Exception as e:
            print(f"Test Execution Failed: {e}")
        finally:
            await self.pw.close()
            # The video file needs time to flush, so it's already handled by close()
            # Update video path in report after close to ensure it's there
            self.report.set_video(video_dir)
            report_path = self.report.generate()
            print(f"Automation finished. Check report at {report_path}")
