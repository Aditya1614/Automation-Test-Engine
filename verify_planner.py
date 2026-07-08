import asyncio
import json
from core.step_planner_agent import StepPlannerAgent
from dotenv import load_dotenv

load_dotenv()

async def main():
    tc = json.load(open('data/flows/p2p-migration/test_cases.json', encoding='utf-8'))[0]
    planner = StepPlannerAgent()
    steps = await planner.plan_steps_for_scenarios(tc['scenarios'])
    print(f'Generated {len(steps)} steps across {len(set(s.get("scenario_name") for s in steps))} scenarios')
    for s in steps:
        print(f'  [{s.get("scenario_name")}] {s.get("step_num")}: {s.get("name")} ({s.get("action_hint")})')

if __name__ == "__main__":
    asyncio.run(main())
