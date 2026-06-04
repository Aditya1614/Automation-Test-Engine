import asyncio
import sys

# Ensure the root directory is in the python path
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from tests.test01_sales_customer_offer import OdooTestRunner

async def main():
    print("Starting Playwright POC Automation with ADK/Gemini...")
    runner = OdooTestRunner()
    await runner.execute()

if __name__ == "__main__":
    asyncio.run(main())
