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
    "action_hint": "string", // One of: "click", "fill", "fill_and_enter", "verify"
    "value": "string or null", // The data to fill, if action_hint is fill or fill_and_enter
    "expected_result": "string or null", // Required if action_hint is "verify". The condition to check.
    "optional": boolean // Default false. Set true ONLY for steps that handle popups/dialogs that may or may not appear.
}

Rules & Odoo 19 Knowledge:
1. Always translate the steps literally but optimize for the UI (e.g., if a step says "Input email", action_hint should be "fill", and provide the email value from Test Data).
2. CRITICAL: The test executor AUTOMATICALLY handles login and navigates to Odoo. You must NEVER generate steps for:
   - Opening/navigating to any URL
   - Inputting email/password for login
   - Clicking the "Log in" button
   - Verifying login success
   Your first step should be the FIRST REAL action AFTER login (e.g., clicking "Sales" module).
3. The final step MUST ALWAYS be a "verify" step that checks the "Expected Results". For negative test cases (where failure/error is expected), the "verify" step should check that the specific error message is shown.
4. For Odoo Many2one dropdowns (like Customer or Product), use action_hint: "fill_and_enter" so the automation presses Enter to trigger the dropdown search.
5. Odoo field naming hints you should include in the "task" description to help the DOM Analyzer:
   - For any field, explicitly tell the AI to use: `div[name='<field_name>'] input`
   - Customer = 'partner_id'
   - Product = 'product_id'
   - Type = 'type'
   - Order Date = 'date_order'
   - Expiration Date = 'validity_date'
   - Quantity = 'product_uom_qty'
6. Be smart about correlating "Test Data" lines to the "Test Steps".
7. DETERMINISM: Only generate steps that are EXPLICITLY described in the test case "Test Steps". Do NOT invent extra anticipatory steps like "Click OK if popup appears" unless the test steps explicitly mention it. If a confirmation popup is part of the expected flow (e.g., after clicking "Confirm"), mark that step as "optional": true.
8. Return ONLY the JSON array.
"""

class StepPlannerAgent:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.client = Client()
        self.model_name = model_name

    async def plan_steps(self, test_case: dict) -> list:
        from datetime import datetime
        current_date_str = datetime.now().strftime("%m/%d/%Y")
        
        dynamic_instruction = PLANNER_INSTRUCTION + f"""
9. DATE vs DROPDOWN RULES (CRITICAL - DO NOT VIOLATE):
   - 'Order Date' (date_order): This is a DATE PICKER. Current date = {current_date_str}. Use action_hint "fill" with the date in MM/DD/YYYY format.
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
        
        Test Data: 
        {test_case.get('test_data', '')}
        
        Expected Results: 
        {test_case.get('expected_results', '')}
        
        Generate the JSON array of steps.
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
