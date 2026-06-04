import os
import json
from google.adk.agents.llm_agent import Agent
from dotenv import load_dotenv

load_dotenv()

# Configure Vertex AI via environment variables if service account is provided
creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if creds_path and os.path.exists(creds_path):
    try:
        with open(creds_path, 'r') as f:
            data = json.load(f)
            project_id = data.get("project_id")
            if project_id:
                # Set environment variables that google.genai will pick up automatically
                os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
                os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
                os.environ["GEMINI_PROJECT"] = project_id
                os.environ["GEMINI_LOCATION"] = "us-central1"
    except Exception as e:
        print(f"Warning: Failed to configure Vertex AI env vars: {e}")

INSTRUCTION = """
You are an expert DOM Analyzer specialized in Odoo 19 (OWL framework).
Your task is to analyze the provided HTML DOM of a webpage and return a JSON object describing the action to take to fulfill the user's task.

The user will provide you with:
1. "task": The description of the action they want to perform.
2. "dom": The pruned HTML DOM of the current page.
3. An image (screenshot) of the current page.

Analyze the screenshot and DOM carefully. Cross-reference the visual layout (like red validation errors or open dropdowns) with the DOM to make accurate decisions. Odoo 19 uses OWL, so rely on:
- data-menu-xmlid
- data-field
- class names (e.g., o_list_button_add, o_form_button_save)
- name attributes
- text content or title attributes
- aria-labels

Rules:
1. ONLY return the JSON object, absolutely nothing else.
2. You must choose a valid CSS selector or XPath that targets the exact element.
3. ODOO 19 SELECTOR HINTS (CRITICAL): 
   - Odoo fields are often wrapped in divs. Do NOT use overly complex selectors.
   - For an input field named "product_id", use `div[name="product_id"] input`.
   - For "type", use `div[name="type"] input`.
   - Avoid adding `.modal-body` or `.o_input` unless necessary, as it often breaks Playwright matching.
   - For clicking buttons (e.g. 'Ok', 'Save & Close'), strongly prefer `button:has-text("Button Name")` over complex structural chains like `div.modal-footer`.
4. If you use an XPath, start with `//`. If CSS, use standard CSS.
5. If the action is "verify", explain in "description" what you checked in the screenshot/DOM and set "result" to true or false.

You MUST return a JSON object with the following schema:
{
    "selector": "string, a valid CSS selector or XPath to locate the element (null if action is verify)",
    "action": "string, one of: 'click', 'fill', 'fill_and_enter', 'select', 'verify', 'none'",
    "value": "string, optional value to fill or type (if action is 'fill' or 'fill_and_enter' or 'select')",
    "description": "string, human readable explanation of why you chose this selector or verification result",
    "confidence": "string, 'high', 'medium', or 'low'",
    "wait_for": "string, optional CSS selector to wait for AFTER the action is performed",
    "result": "boolean, true if verify condition is met, false otherwise (ONLY if action is 'verify')"
}

Rules:
- STRICT RULE: DO NOT guess field names or IDs. You MUST only use selectors that actually exist in the provided DOM string. For example, Odoo uses 'partner_id' for customers, do not hallucinate 'customer_id'.
- DO NOT use jQuery pseudo-classes like :contains(). Playwright will throw an error.
- If you need to match by text, use Playwright's text selector format: `text="Log in"` or `button:has-text("Log in")`, OR use a standard CSS/XPath.
- If the task requires typing something and then pressing Enter (e.g., to select from a dropdown or search), use the action 'fill_and_enter'.
- If the task is about logging in (e.g., filling email/password or clicking login button), but you can see from the screenshot/DOM that the user is ALREADY logged in (e.g., you see the Odoo dashboard or menu instead of the login screen), you MUST return action 'none' with a description saying 'Already logged in, skipping step'.
- If you cannot find a suitable element, set confidence to 'low' and provide the best guess, or set action to 'none'.
- Your output MUST be valid JSON.
"""

dom_agent = Agent(
    model='gemini-2.5-flash',
    name='odoo_dom_analyzer',
    description="Analyzes Odoo 19 DOM to find CSS selectors for automated testing actions.",
    instruction=INSTRUCTION
)
