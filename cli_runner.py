import argparse
import asyncio
import json
import os
import sys

# Ensure the root directory is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.excel_parser import TestCaseParser
from core.step_planner_agent import StepPlannerAgent
from core.test_executor import TestExecutor

async def run_single_test(test_case: dict):
    print(f"\n--- Planning Steps for Test Case: {test_case.get('id', 'Unknown')} ---")
    planner = StepPlannerAgent()
    try:
        planned_steps = await planner.plan_steps(test_case)
        print("Planned Steps:")
        print(json.dumps(planned_steps, indent=2))
        test_case['steps'] = planned_steps
    except Exception as e:
        print(f"Failed to plan steps: {e}")
        return

    executor = TestExecutor()
    result = await executor.execute(test_case)
    print(f"\nTest Result: {result['status']} (Tokens used: {result.get('total_tokens', 0)})")

async def main():
    parser = argparse.ArgumentParser(description="SIT Dynamic Test Runner")
    parser.add_argument("--json", type=str, help="Path to JSON test case file")
    parser.add_argument("--excel", type=str, help="Path to Excel SIT export file")
    parser.add_argument("--test-id", type=str, help="Run specific test case ID from Excel")
    parser.add_argument("--all", action="store_true", help="Run all test cases in the Excel file sequentially")
    
    args = parser.parse_args()

    if args.json:
        if not os.path.exists(args.json):
            print(f"File not found: {args.json}")
            return
        with open(args.json, 'r') as f:
            test_case = json.load(f)
        await run_single_test(test_case)

    elif args.excel:
        if not os.path.exists(args.excel):
            print(f"File not found: {args.excel}")
            return
            
        parser = TestCaseParser(args.excel)
        test_cases = parser.parse()
        print(f"Found {len(test_cases)} test cases in {args.excel}")
        
        if args.test_id:
            target_tc = next((tc for tc in test_cases if tc['id'] == args.test_id), None)
            if not target_tc:
                print(f"Test Case {args.test_id} not found in Excel file.")
                return
            await run_single_test(target_tc)
            
        elif args.all:
            for i, tc in enumerate(test_cases):
                print(f"\nExecuting {i+1}/{len(test_cases)}: {tc.get('id')}")
                await run_single_test(tc)
        else:
            print("Please specify --test-id <ID> or --all when using --excel")
            
    else:
        print("Please provide --json or --excel input. Use -h for help.")

if __name__ == "__main__":
    asyncio.run(main())
