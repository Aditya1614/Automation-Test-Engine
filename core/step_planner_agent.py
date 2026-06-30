import json
from google.genai import Client, types

PLANNER_INSTRUCTION = """
You are an expert Test Step Planner specialized in Odoo 19 testing automation.
Your task is to take a raw test case description (Test Steps, Test Data, Expected Results) and convert it into a structured JSON array of executable steps for an automation engine.

The output MUST be a valid JSON array of objects.
Each object must represent a single interaction step, matching this schema:
{
    "step_num": float, // e.g., 1, 1.1, 2, 3
    "name": "string", // Short name, e.g., "Input Email"
    "task": "string", // Detailed instruction in Indonesian on what to do. Include hints for Odoo field names if applicable.
    "action_hint": "string", // One of: "click", "fill", "fill_and_enter", "fill_and_choose", "verify", "upload_file"
    "value": "string or null", // The data to fill, if action_hint is fill, fill_and_enter, or fill_and_choose
    "expected_result": "string or null", // Required if action_hint is "verify". The condition to check.
    "optional": boolean // Default false. Set true ONLY for steps that handle popups/dialogs that may or may not appear.
}

Rules & Odoo 19 Knowledge:
1. Always translate the steps literally but optimize for the UI (e.g., if a step says "Input email", action_hint should be "fill", and provide the email value from Test Data).
2. CRITICAL LOGIN RULES:
   - The test executor AUTOMATICALLY handles the INITIAL login. Your first step should be the FIRST REAL action AFTER login (e.g., clicking "Sales" module).
   - NEVER generate steps for inputting email/password or clicking "Log in".
   - If the test_step_detail contains multiple "Login sebagai: <name>" directives, it means the test requires SWITCHING USERS mid-test. For each user switch AFTER the first login, generate a single step with:
     "action_hint": "switch_user", "value": "<exact user name>", "name": "Switch to <user name>"
   - The executor will handle the actual logout/login automatically.
   - Continue generating normal action steps after the switch_user step.
3. The final step MUST ALWAYS be a "verify" step that checks the "Expected Results". For negative test cases (where failure/error is expected), the "verify" step should check that the specific error message is shown.
4. For Odoo Many2one dropdowns (like Customer or Product), use action_hint: "fill_and_choose" so the automation types the value, waits for the dropdown, and clicks the matching option.
5. Odoo field naming hints you should include in the "task" description to help the DOM Analyzer:
   - For any field, explicitly tell the AI to use: `div[name='<field_name>'] input`
   - Customer = 'partner_id' (ONLY use this when filling a form view to create/edit a record. DO NOT use this when searching for a customer in a list view).
   - Product = 'product_id'
   - Type = 'type'
   - Order Date = 'date_order'
   - Expiration Date = 'validity_date'
   - Quantity = 'product_uom_qty'
   - LIST VIEW SEARCHES: If the step involves finding or selecting a record immediately after opening a menu (which implies a list view), you MUST generate TWO SEPARATE STEPS:
     1. Search step: action_hint="fill_and_enter", using the main search bar selector `input.o_searchview_input` with the search value.
     2. Click result step: action_hint="click", with a task description to click the specific record in the search results to open its form view.
   - For standard Odoo buttons, include these CSS selectors in the task description:
     - 'New' button (creating new record) = `button.o_list_button_add`
     - 'Add a product' / 'Add a line' = `a:has-text("Add a product"), a:has-text("Add a line")`
6. Be smart about correlating "Test Data" lines to the "Test Steps".
7. DETERMINISM & STRICT ORDERING (CRITICAL):
   - You MUST generate steps in the EXACT same sequence as they appear in the "Test Step Detail".
   - DO NOT reorder steps under any circumstances (e.g. do not move a step before another if it was written after).
   - DO NOT combine or skip any manual actions. If there are multiple actions listed, generate separate steps for EACH distinct action.
   - Only generate steps that are EXPLICITLY described. Do NOT invent anticipatory steps.
8. ODOO 19 MENU NAVIGATION (CRITICAL): Odoo 19 uses a top navigation bar.
   - If the user explicitly defines intermediate tabs, menus, or navbar items (e.g., "klik tab master", "Klik 'Sales' pada navbar"), you MUST generate individual steps for EACH click exactly as specified. Do NOT assume a navbar click is redundant with a module click. Do NOT abstract, combine, or skip intermediate tabs/navbars.
   - Example: If the instructions say "Klik module Sales", "Klik 'Sales' pada navbar", "Klik 'Customer Offers'", you MUST generate 3 separate steps:
     1. Click 'Sales' module
     2. Click 'Sales' on navbar
     3. Click 'Customer Offers' menu
   - If the user simply says "Click menu X under Y", then generate two steps (Click Y, then Click X). DO NOT combine them into one step.
   - Note: In the Odoo 19 Sales module, 'Quotations' is typically under the 'Sales' top menu.
9. FILE UPLOAD STEPS: If the test steps mention uploading a file (e.g., "Upload file MIGRASI19-P2P-VENDCLASS-005.csv"), generate a step with:
   - action_hint: "upload_file"
   - value: "<exact filename>" (e.g., "MIGRASI19-P2P-VENDCLASS-005.csv")
   - task: Description of the upload action and the file input selector to target.
   The automation engine will resolve the file path from the flow's managed file store.
10. CHECKBOXES: If the step says "centang" or "check" a specific field, use action_hint "click" and specifically mention in the task to "Klik checkbox [Name of Checkbox]". Do NOT use the partner_id or other input selectors for checkboxes.
11. Return ONLY the JSON array.
"""

class StepPlannerAgent:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.client = Client()
        self.model_name = model_name

    async def plan_steps(self, test_case: dict) -> list:
        from datetime import datetime
        current_date_str = datetime.now().strftime("%m/%d/%Y")
        
        dynamic_instruction = PLANNER_INSTRUCTION + f"""
12. DATE vs DROPDOWN RULES (CRITICAL - DO NOT VIOLATE):
   - 'Order Date' (date_order): This is a DATE PICKER. Current date = {current_date_str}. Use action_hint "fill_and_enter" with the date in MM/DD/YYYY format so the picker popup closes.
   - 'Valid Date' / 'Expiration' (validity_date): This is a DROPDOWN, NOT a date picker! NEVER compute a date for this field!
     You MUST use action_hint "fill_and_enter" with the LITERAL dropdown option text from the test case (e.g., "14 Days", "30 Days").
     If the test says "14 Days", use value "14 Days". If it says "30 Days", use value "30 Days".
     WRONG: "value": "06/16/2026"  ← NEVER DO THIS for Valid Date!
     CORRECT: "value": "14 Days"   ← Always use the literal text!
"""
        
        prompt = f"""
        Pre-Conditions: {test_case.get('pre_conditions', '')}
        
        Test Steps: 
        {test_case.get('test_steps', '')}
        
        Test Step Detail:
        {test_case.get('test_step_detail', '')}
        
        Test Data: 
        {test_case.get('test_data', '')}
        
        Expected Results: 
        {test_case.get('expected_results', '')}
        
        Generate the JSON array of steps. Use Test Steps and Test Step Detail to figure out the exact granular actions.
        """
        
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=dynamic_instruction,
                temperature=0.2
            )
        )
        
        import re
        match = re.search(r'\[.*\]', response.text, re.DOTALL)
        if match:
            clean_text = match.group(0)
        else:
            clean_text = response.text
            
        try:
            return json.loads(clean_text)
        except Exception as e:
            print(f"Failed to parse Planner AI response: {response.text}")
            raise e
