"""Task planner module for analyzing and decomposing complex tasks."""

from horbot.agent.planner.storage import PlanStorage, get_plan_storage, ExecutionPlan, SubTask

__all__ = [
    "PlanStorage",
    "get_plan_storage", 
    "ExecutionPlan",
    "SubTask",
]


class TaskPlanner:
    COMPLEXITY_KEYWORDS = {
        "high": [
            "重构", "重写", "迁移", "实现", "创建项目", "搭建",
            "多个文件", "批量", "全部", "整个项目", "系统",
            "集成", "部署", "测试套件", "文档生成"
        ],
        "medium": [
            "修改", "更新", "添加", "删除", "创建", "编写",
            "分析", "优化", "修复", "配置"
        ],
        "low": [
            "查看", "列出", "显示", "读取", "获取", "搜索",
            "解释", "说明", "是什么", "怎么样"
        ]
    }
    
    MULTI_STEP_INDICATORS = [
        "然后", "接着", "之后", "同时", "并且",
        "第一步", "第二步", "首先", "最后",
        "以及", "还有", "另外"
    ]
    
    def analyze_complexity(self, task: str) -> str:
        task_lower = task.lower()
        
        for keyword in self.COMPLEXITY_KEYWORDS["high"]:
            if keyword in task_lower:
                return "high"
        
        step_count = sum(1 for indicator in self.MULTI_STEP_INDICATORS if indicator in task_lower)
        if step_count >= 2:
            return "high"
        
        for keyword in self.COMPLEXITY_KEYWORDS["medium"]:
            if keyword in task_lower:
                return "medium"
        
        for keyword in self.COMPLEXITY_KEYWORDS["low"]:
            if keyword in task_lower:
                return "low"
        
        word_count = len(task.split())
        if word_count > 50:
            return "high"
        elif word_count > 20:
            return "medium"
        
        return "low"
    
    def needs_planning(self, task: str) -> bool:
        complexity = self.analyze_complexity(task)
        return complexity in ("high", "medium")
    
    def generate_plan_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import uuid
        short_id = uuid.uuid4().hex[:6]
        return f"plan_{timestamp}_{short_id}"
    
    def create_plan(
        self,
        task: str,
        subtasks: list[dict],
        session_key: str = "",
        message_id: str = ""
    ) -> ExecutionPlan:
        plan_id = self.generate_plan_id()
        
        subtask_objs = []
        for i, st in enumerate(subtasks):
            subtask_objs.append(SubTask(
                id=f"{plan_id}_subtask_{i+1}",
                title=st.get("title", f"子任务 {i+1}"),
                description=st.get("description", ""),
                status="pending",
                tools=st.get("tools", []),
            ))
        
        plan = ExecutionPlan(
            id=plan_id,
            title=task[:100] + ("..." if len(task) > 100 else ""),
            description=task,
            subtasks=subtask_objs,
            status="pending",
            session_key=session_key,
            message_id=message_id,
        )
        
        storage = get_plan_storage()
        storage.save_plan(plan)
        
        return plan
    
    def update_subtask_status(
        self,
        plan: ExecutionPlan,
        subtask_id: str,
        status: str,
        result: str = ""
    ) -> ExecutionPlan:
        for subtask in plan.subtasks:
            if subtask.id == subtask_id:
                subtask.status = status
                if result:
                    subtask.result = result
                break
        
        storage = get_plan_storage()
        storage.save_plan(plan)
        
        return plan


_planner: Optional[TaskPlanner] = None


def get_task_planner() -> TaskPlanner:
    global _planner
    if _planner is None:
        _planner = TaskPlanner()
    return _planner
