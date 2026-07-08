import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

class ReportGenerator:
    def __init__(self, template_dir="templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
        self.template = self.env.get_template("report.html")
        self.results = []
        self.test_info = {
            "test_id": "-",
            "test_title": "-",
            "type": "-",
            "expected_results": "-",
            "actual_results": "-",
            "total_tokens": 0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": "https://odoo19-dev.porto.co.id/",
            "browser": "Chromium (Playwright)",
            "video_path": ""
        }
        self.scenarios = []
        self.current_scenario_name = None
        self.current_scenario = None

    def start_scenario(self, name: str, expected_results: str):
        self.current_scenario = {
            "name": name,
            "expected_results": expected_results,
            "actual_results": "",
            "status": "PASS",
            "steps": []
        }
        self.scenarios.append(self.current_scenario)

    def end_scenario(self, name: str, passed: bool, actual_results: str = ""):
        if self.current_scenario:
            self.current_scenario["status"] = "PASS" if passed else "FAIL"
            self.current_scenario["actual_results"] = actual_results

    def set_current_step_scenario(self, name: str):
        self.current_scenario_name = name

    def add_result(self, step_num: float, step_name: str, task: str, status: str, 
                   selector: str = "-", action: str = "-", confidence: str = "-", 
                   screenshot_path: str = "", error_msg: str = ""):
        # Convert path to relative for HTML
        rel_screenshot = screenshot_path.replace("test-results/", "") if screenshot_path else ""
        
        self.results.append({
            "step_num": step_num,
            "step_name": step_name,
            "task": task,
            "status": status,
            "selector": selector,
            "action": action,
            "confidence": confidence,
            "screenshot": rel_screenshot,
            "error_msg": error_msg,
            "scenario_name": self.current_scenario_name
        })

    def set_video(self, video_dir: str):
        # Find the .webm file in the directory
        if not video_dir or not os.path.exists(video_dir):
            return
            
        for file in os.listdir(video_dir):
            if file.endswith(".webm"):
                # Use relative path from test-results
                self.test_info["video_path"] = f"{os.path.basename(video_dir)}/{file}"
                break

    def generate(self):
        timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test-results/report-{timestamp_file}.html"
        
        # Calculate summary
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = total - passed
        
        summary = {
            "total": total,
            "passed": passed,
            "failed": failed
        }
        
        html_content = self.template.render(
            test_info=self.test_info,
            summary=summary,
            results=self.results,
            scenarios=self.scenarios
        )
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        print(f"Report generated: {filename}")
        return filename
