"""Plan storage module for persisting execution plans."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class SubTask:
    id: str
    title: str
    description: str = ""
    status: str = "pending"
    tools: list[str] = field(default_factory=list)
    result: str = ""


@dataclass
class PlanSpec:
    """Detailed specification for a plan."""
    why: str = ""
    what_changes: list[str] = field(default_factory=list)
    impact: dict = field(default_factory=dict)


@dataclass
class PlanChecklist:
    """Checklist for plan verification."""
    items: list[dict] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    id: str
    title: str
    description: str
    subtasks: list[SubTask] = field(default_factory=list)
    status: str = "pending"
    created_at: str = ""
    updated_at: str = ""
    session_key: str = ""
    message_id: str = ""
    spec: PlanSpec = field(default_factory=PlanSpec)
    checklist: PlanChecklist = field(default_factory=PlanChecklist)
    spec_content: str = ""
    tasks_content: str = ""
    checklist_content: str = ""
    plan_type: str = "actionable"  # "informational" or "actionable"
    content: str = ""  # Plan content for informational plans

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


class PlanStorage:
    def __init__(self, base_path: str = None):
        if base_path:
            self.base_path = Path(base_path)
        else:
            from horbot.utils.paths import get_plans_dir
            self.base_path = get_plans_dir()
        self.plans_path = self.base_path
        self.index_path = self.plans_path / "index.json"
        self._ensure_directories()
    
    def _ensure_directories(self):
        self.plans_path.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._save_index({"plans": []})
    
    def _load_index(self) -> dict:
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"plans": []}
    
    def _save_index(self, index: dict):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    
    def _progress_label(self, subtasks: list[SubTask]) -> str:
        completed = sum(1 for s in subtasks if s.status == "completed")
        return f"{completed}/{len(subtasks)} 完成"
    
    def save_plan(self, plan: ExecutionPlan) -> str:
        plan.updated_at = datetime.now().isoformat()
        
        plan_dir = self.plans_path / plan.id
        plan_dir.mkdir(parents=True, exist_ok=True)
        
        spec_file = plan_dir / "spec.md"
        with open(spec_file, "w", encoding="utf-8") as f:
            f.write(plan.spec_content)
        
        tasks_file = plan_dir / "tasks.md"
        with open(tasks_file, "w", encoding="utf-8") as f:
            f.write(plan.tasks_content)
        
        checklist_file = plan_dir / "checklist.md"
        with open(checklist_file, "w", encoding="utf-8") as f:
            f.write(plan.checklist_content)
        
        index = self._load_index()
        plan_info = {
            "id": plan.id,
            "title": plan.title,
            "description": plan.description,
            "status": plan.status,
            "progress": self._progress_label(plan.subtasks),
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
            "session_key": plan.session_key,
            "message_id": plan.message_id,
            "plan_type": plan.plan_type,
            "content": plan.content,
            "subtasks": [
                {
                    "id": st.id,
                    "title": st.title,
                    "description": st.description,
                    "status": st.status,
                    "tools": st.tools,
                }
                for st in plan.subtasks
            ],
            "spec": {
                "why": plan.spec.why if plan.spec else "",
                "what_changes": plan.spec.what_changes if plan.spec else [],
                "impact": plan.spec.impact if plan.spec else {},
            },
            "checklist": {
                "items": plan.checklist.items if plan.checklist else [],
            },
        }
        
        existing = next((p for p in index["plans"] if p["id"] == plan.id), None)
        if existing:
            index["plans"].remove(existing)
        index["plans"].append(plan_info)
        self._save_index(index)
        
        return str(plan_dir)
    
    def load_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        plan_dir = self.plans_path / plan_id
        if not plan_dir.exists():
            return None
        
        index = self._load_index()
        plan_info = next((p for p in index["plans"] if p["id"] == plan_id), None)
        
        if not plan_info:
            return None
        
        subtasks = [
            SubTask(
                id=st.get("id", ""),
                title=st.get("title", ""),
                description=st.get("description", ""),
                status=st.get("status", "pending"),
                tools=st.get("tools", []),
            )
            for st in plan_info.get("subtasks", [])
        ]
        
        spec_data = plan_info.get("spec", {})
        spec = PlanSpec(
            why=spec_data.get("why", ""),
            what_changes=spec_data.get("what_changes", []),
            impact=spec_data.get("impact", {}),
        )
        
        checklist_data = plan_info.get("checklist", {})
        checklist = PlanChecklist(
            items=checklist_data.get("items", []),
        )
        
        spec_content = ""
        tasks_content = ""
        checklist_content = ""
        
        spec_file = plan_dir / "spec.md"
        if spec_file.exists():
            with open(spec_file, "r", encoding="utf-8") as f:
                spec_content = f.read()
        
        tasks_file = plan_dir / "tasks.md"
        if tasks_file.exists():
            with open(tasks_file, "r", encoding="utf-8") as f:
                tasks_content = f.read()
        
        checklist_file = plan_dir / "checklist.md"
        if checklist_file.exists():
            with open(checklist_file, "r", encoding="utf-8") as f:
                checklist_content = f.read()
        
        return ExecutionPlan(
            id=plan_id,
            title=plan_info.get("title", ""),
            description=plan_info.get("description", ""),
            subtasks=subtasks,
            status=plan_info.get("status", "pending"),
            created_at=plan_info.get("created_at", ""),
            updated_at=plan_info.get("updated_at", ""),
            session_key=plan_info.get("session_key", ""),
            message_id=plan_info.get("message_id", ""),
            spec=spec,
            checklist=checklist,
            spec_content=spec_content,
            tasks_content=tasks_content,
            checklist_content=checklist_content,
            plan_type=plan_info.get("plan_type", "actionable"),
            content=plan_info.get("content", ""),
        )
    
    def update_plan_status(self, plan_id: str, status: str) -> bool:
        index = self._load_index()
        plan_info = next((p for p in index["plans"] if p["id"] == plan_id), None)
        
        if not plan_info:
            return False
        
        plan_info["status"] = status
        self._save_index(index)
        return True
    
    def update_subtask_status(self, plan_id: str, subtask_id: str, status: str) -> bool:
        index = self._load_index()
        plan_info = next((p for p in index["plans"] if p["id"] == plan_id), None)
        
        if not plan_info:
            return False
        
        for subtask in plan_info.get("subtasks", []):
            if subtask.get("id") == subtask_id:
                subtask["status"] = status
                break
        
        plan_info["progress"] = self._progress_label([
            SubTask(**st) for st in plan_info.get("subtasks", [])
        ])
        
        self._save_index(index)
        
        plan_dir = self.plans_path / plan_id
        tasks_file = plan_dir / "tasks.md"
        
        if tasks_file.exists():
            plan = self.load_plan(plan_id)
            if plan:
                updated_tasks = self._update_tasks_md_status(plan.tasks_content, subtask_id, status)
                with open(tasks_file, "w", encoding="utf-8") as f:
                    f.write(updated_tasks)
        
        return True
    
    def _update_tasks_md_status(self, tasks_content: str, subtask_id: str, status: str) -> str:
        """Update the status of a task in tasks.md content."""
        lines = tasks_content.split("\n")
        result_lines = []
        
        # Convert subtask_id (step_1) to task number (1)
        task_number = None
        if subtask_id.startswith("step_"):
            try:
                task_number = int(subtask_id.split("_")[1])
            except (IndexError, ValueError):
                pass
        
        for line in lines:
            # Match task by number (e.g., "## [ ] Task 1:" or "## [x] Task 1:")
            if task_number and f"Task {task_number}:" in line:
                if status == "completed":
                    line = line.replace("[ ]", "[x]")
                else:
                    line = line.replace("[x]", "[ ]")
            # Also try to match by subtask_id for backward compatibility
            elif f"Task" in line and subtask_id in line:
                if status == "completed":
                    line = line.replace("[ ]", "[x]")
                else:
                    line = line.replace("[x]", "[ ]")
            result_lines.append(line)
        
        return "\n".join(result_lines)
    
    def update_checklist_item(self, plan_id: str, item_id: str, checked: bool) -> bool:
        index = self._load_index()
        plan_info = next((p for p in index["plans"] if p["id"] == plan_id), None)
        
        if not plan_info:
            return False
        
        for item in plan_info.get("checklist", {}).get("items", []):
            if item.get("id") == item_id:
                item["checked"] = checked
                break
        
        self._save_index(index)
        
        plan_dir = self.plans_path / plan_id
        checklist_file = plan_dir / "checklist.md"
        
        if checklist_file.exists():
            plan = self.load_plan(plan_id)
            if plan:
                updated_checklist = self._update_checklist_md_status(plan.checklist_content, item_id, checked)
                with open(checklist_file, "w", encoding="utf-8") as f:
                    f.write(updated_checklist)
        
        return True
    
    def _update_checklist_md_status(self, checklist_content: str, item_id: str, checked: bool) -> str:
        """Update the status of a checklist item in checklist.md content."""
        lines = checklist_content.split("\n")
        result_lines = []
        
        for line in lines:
            if item_id in line or (checked and "[ ]" in line):
                if checked:
                    line = line.replace("[ ]", "[x]")
                else:
                    line = line.replace("[x]", "[ ]")
            result_lines.append(line)
        
        return "\n".join(result_lines)
    
    def list_plans(self, session_key: Optional[str] = None) -> list[dict]:
        index = self._load_index()
        plan_infos = index.get("plans", [])
        
        if session_key:
            plan_infos = [p for p in plan_infos if p.get("session_key") == session_key]
        
        full_plans = []
        for plan_info in plan_infos:
            plan_id = plan_info.get("id")
            if plan_id:
                full_plan = self.load_plan(plan_id)
                if full_plan:
                    full_plans.append({
                        "id": full_plan.id,
                        "title": full_plan.title,
                        "description": full_plan.description,
                        "status": full_plan.status,
                        "created_at": full_plan.created_at,
                        "updated_at": full_plan.updated_at,
                        "session_key": full_plan.session_key,
                        "message_id": full_plan.message_id,
                        "subtasks": [
                            {
                                "id": st.id,
                                "title": st.title,
                                "description": st.description,
                                "status": st.status,
                                "tools": st.tools,
                            }
                            for st in full_plan.subtasks
                        ],
                        "spec": {
                            "why": full_plan.spec.why if full_plan.spec else "",
                            "what_changes": full_plan.spec.what_changes if full_plan.spec else [],
                            "impact": full_plan.spec.impact if full_plan.spec else {},
                        },
                        "checklist": {
                            "items": full_plan.checklist.items if full_plan.checklist else [],
                        },
                        "spec_content": full_plan.spec_content,
                        "tasks_content": full_plan.tasks_content,
                        "checklist_content": full_plan.checklist_content,
                        "plan_type": full_plan.plan_type,
                        "content": full_plan.content,
                    })
        
        return full_plans
    
    def save_execution_logs(self, plan_id: str, subtask_id: str, logs: list) -> bool:
        """Save execution logs for a subtask.
        
        Args:
            plan_id: The plan ID
            subtask_id: The subtask ID
            logs: List of log entries
            
        Returns:
            True if saved successfully, False otherwise
        """
        plan_dir = self.plans_path / plan_id
        if not plan_dir.exists():
            return False
        
        logs_file = plan_dir / f"logs_{subtask_id}.json"
        
        try:
            import json
            with open(logs_file, "w", encoding="utf-8") as f:
                json.dump({
                    "plan_id": plan_id,
                    "subtask_id": subtask_id,
                    "logs": logs,
                    "updated_at": datetime.now().isoformat(),
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving execution logs: {e}")
            return False
    
    def load_execution_logs(self, plan_id: str, subtask_id: str) -> Optional[dict]:
        """Load execution logs for a subtask.
        
        Args:
            plan_id: The plan ID
            subtask_id: The subtask ID
            
        Returns:
            Dict with logs data, or None if not found
        """
        plan_dir = self.plans_path / plan_id
        if not plan_dir.exists():
            return None
        
        logs_file = plan_dir / f"logs_{subtask_id}.json"
        if not logs_file.exists():
            return None
        
        try:
            import json
            with open(logs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading execution logs: {e}")
            return None
    
    def load_all_execution_logs(self, plan_id: str) -> dict:
        """Load all execution logs for a plan.
        
        Args:
            plan_id: The plan ID
            
        Returns:
            Dict mapping subtask_id to logs data
        """
        plan_dir = self.plans_path / plan_id
        if not plan_dir.exists():
            return {}
        
        all_logs = {}
        for logs_file in plan_dir.glob("logs_*.json"):
            try:
                import json
                with open(logs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    subtask_id = data.get("subtask_id")
                    if subtask_id:
                        all_logs[subtask_id] = data
            except Exception as e:
                print(f"Error loading execution logs from {logs_file}: {e}")
        
        return all_logs


_storage: Optional[PlanStorage] = None


def get_plan_storage() -> PlanStorage:
    global _storage
    if _storage is None:
        _storage = PlanStorage()
    return _storage
