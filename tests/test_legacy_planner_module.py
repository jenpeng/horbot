import importlib.util
import unittest
from pathlib import Path


class LegacyPlannerModuleTests(unittest.TestCase):
    def test_legacy_planner_file_can_be_loaded_directly(self):
        planner_path = Path(__file__).resolve().parents[1] / "horbot" / "agent" / "planner.py"
        spec = importlib.util.spec_from_file_location("legacy_planner", planner_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        planner = module.get_task_planner()
        plan_id = planner.generate_plan_id()

        self.assertTrue(plan_id.startswith("plan_"))
        self.assertIs(planner, module.get_task_planner())


if __name__ == "__main__":
    unittest.main()
