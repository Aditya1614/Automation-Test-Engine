import os
import json
from datetime import datetime
from typing import List, Dict, Optional

class FlowManager:
    def __init__(self, saved_flows_dir: str = "saved_flows"):
        self.saved_flows_dir = saved_flows_dir
        if not os.path.exists(self.saved_flows_dir):
            os.makedirs(self.saved_flows_dir)

    def _get_file_path(self, test_case_id: str) -> str:
        # Sanitize filename
        safe_id = "".join([c for c in test_case_id if c.isalnum() or c in ('-', '_')]).rstrip()
        return os.path.join(self.saved_flows_dir, f"{safe_id}.json")

    def save_flow(self, test_case_id: str, planned_steps: List[Dict], executed_actions: List[Dict]):
        """Saves a successfully executed flow to disk."""
        data = {
            "test_case_id": test_case_id,
            "saved_at": datetime.now().isoformat(),
            "planned_steps": planned_steps,
            "executed_actions": executed_actions
        }
        
        file_path = self._get_file_path(test_case_id)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return file_path

    def load_flow(self, test_case_id: str) -> Optional[Dict]:
        """Loads a saved flow from disk."""
        file_path = self._get_file_path(test_case_id)
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading saved flow for {test_case_id}: {e}")
            return None

    def has_saved_flow(self, test_case_id: str) -> bool:
        """Checks if a saved flow exists for the given test case ID."""
        return os.path.exists(self._get_file_path(test_case_id))

    def delete_flow(self, test_case_id: str) -> bool:
        """Deletes a saved flow."""
        file_path = self._get_file_path(test_case_id)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except OSError:
                return False
        return False

    def list_flows(self) -> List[Dict]:
        """Lists all saved flows."""
        flows = []
        for filename in os.listdir(self.saved_flows_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(self.saved_flows_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        flows.append({
                            "test_case_id": data.get("test_case_id"),
                            "saved_at": data.get("saved_at"),
                            "steps_count": len(data.get("executed_actions", []))
                        })
                except Exception:
                    pass
        return flows
