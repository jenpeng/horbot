"""Task complexity analyzer for determining planning needs."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, TYPE_CHECKING
import re
import json

if TYPE_CHECKING:
    from horbot.providers.base import LLMProvider


class ComplexityLevel(Enum):
    """Complexity levels for tasks."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class ComplexityAnalysis:
    """Result of complexity analysis."""
    level: ComplexityLevel
    score: float
    reasons: list[str]
    suggested_mode: str
    needs_planning: bool
    estimated_steps: int
    plan_type: str = "actionable"  # "informational" or "actionable"


COMPLEXITY_ANALYSIS_PROMPT = """You are a task complexity analyzer. Analyze the given task and determine if it needs planning/breakdown before execution.

Task: {task}

Available tools: {tools}

Analyze the task and respond with a JSON object containing:
1. "needs_planning": boolean - true if the task is complex enough to need planning
2. "complexity_level": "simple" | "moderate" | "complex"
3. "estimated_steps": number of steps needed (1-10)
4. "reasons": array of strings explaining why
5. "confidence": 0.0-1.0 confidence in your assessment
6. "plan_type": "informational" | "actionable" - determine if this is informational (advice, suggestions) or actionable (tasks to execute)

Guidelines for determining complexity:
- SIMPLE (no planning needed):
  - Single, straightforward operations (read a file, answer a question)
  - Information queries (what is, explain, how to)
  - Simple edits or lookups

- MODERATE (may need planning):
  - 2-3 related operations
  - Some decision making required
  - File operations with conditions

- COMPLEX (needs planning):
  - 4+ distinct operations
  - Multiple files or components affected
  - Architecture or structural changes
  - Multi-phase work with dependencies
  - Tasks requiring careful sequencing

Guidelines for determining plan_type:
- INFORMATIONAL: The task asks for advice, suggestions, recommendations, or information about personal life, travel, learning, etc.
  - Examples: "帮我规划五一假期", "给我一些学习建议", "分析一下这个项目的优缺点"
  - These provide information/suggestions but don't require tool execution
  - Key indicators: personal life topics (vacation, travel, study advice, career advice)
- ACTIONABLE: The task requires actual execution of tools or operations to build/create something
  - Examples: "重构代码", "创建文件", "部署服务", "帮我做一个微信小程序"
  - These require executing specific actions with tools
  - Key indicators: development tasks, building apps, creating systems, implementing features

Examples:
- "What is Python?" -> {"needs_planning": false, "complexity_level": "simple", "estimated_steps": 1, "reasons": ["Information query"], "confidence": 0.95, "plan_type": "informational"}
- "Read the config file" -> {"needs_planning": false, "complexity_level": "simple", "estimated_steps": 1, "reasons": ["Single file operation"], "confidence": 0.9, "plan_type": "actionable"}
- "Fix the bug in auth.py" -> {"needs_planning": false, "complexity_level": "moderate", "estimated_steps": 2, "reasons": ["Need to read, understand, and fix"], "confidence": 0.8, "plan_type": "actionable"}
- "Refactor the entire project structure" -> {"needs_planning": true, "complexity_level": "complex", "estimated_steps": 8, "reasons": ["Multiple files affected", "Structural changes", "Needs careful sequencing"], "confidence": 0.9, "plan_type": "actionable"}
- "Create a user authentication system with login, logout, and password reset" -> {"needs_planning": true, "complexity_level": "complex", "estimated_steps": 6, "reasons": ["Multiple features", "Security considerations", "Database changes"], "confidence": 0.85, "plan_type": "actionable"}
- "帮我规划一下五一假期该如何安排" -> {"needs_planning": true, "complexity_level": "moderate", "estimated_steps": 3, "reasons": ["Personal travel planning advice"], "confidence": 0.85, "plan_type": "informational"}
- "帮我做一个微信小程序规划，该小程序允许用户导入word文档" -> {"needs_planning": true, "complexity_level": "complex", "estimated_steps": 8, "reasons": ["Development task requiring multiple features", "App implementation", "Technical requirements"], "confidence": 0.9, "plan_type": "actionable"}

Respond ONLY with the JSON object, no other text."""


class TaskAnalyzer:
    """
    Analyzes task complexity to determine if planning mode is needed.
    
    Uses a three-stage approach:
    1. Quick keyword pre-screening
    2. Rule-based analysis
    3. LLM intelligent judgment (when uncertain)
    """
    
    CLEARLY_SIMPLE_PATTERNS = {
        "what is", "what are", "tell me", "explain", "describe", "define",
        "show me", "how to", "help me understand", "who is", "where is",
        "是什么", "什么是", "解释", "描述", "介绍一下", "怎么",
        "如何理解", "谁是", "哪里是", "为什么", "怎样",
    }

    CLEARLY_SIMPLE_STARTS = {
        "hi", "hello", "hey", "thanks", "thank", "ok", "yes", "no",
        "你好", "您好", "谢谢", "好的", "是", "否", "嗯", "哦",
    }

    CLEARLY_COMPLEX_PATTERNS = {
        "refactor the entire", "rebuild the whole", "migrate the complete",
        "重构整个", "重建整个", "迁移整个", "全面重构",
        "architecture redesign", "system overhaul", "complete rewrite",
        "架构重设计", "系统重构", "完全重写",
        "multiple components", "several modules", "various parts",
        "多个组件", "几个模块", "各个部分",
    }

    # Informational plan patterns - tasks that ask for advice/suggestions
    INFORMATIONAL_PATTERNS = {
        "规划", "建议", "推荐", "分析", "评估", "对比", "比较",
        "plan", "suggest", "recommend", "advice", "analyze", "compare",
        "如何安排", "怎么安排", "给点建议", "有什么建议",
        "假期", "旅行", "旅游", "行程", "攻略",
        "vacation", "travel", "trip", "itinerary",
    }
    
    MULTI_STEP_KEYWORDS = {
        "and then", "after that", "next", "finally", "step by step",
        "first", "second", "third", "then", "after", "before",
        "once done", "when finished", "subsequently",
        "refactor", "migrate", "set up", "configure", "implement",
        "create a", "build a", "develop a", "design a",
        "integrate", "deploy", "automate", "orchestrate",
        "帮我", "请帮我", "帮我写", "帮我创建", "帮我实现",
        "然后", "接着", "之后", "最后", "第一步", "第二步",
        "重构", "迁移", "搭建", "配置", "实现", "创建", "构建",
        "集成", "部署", "自动化", "批量", "整个项目", "所有文件",
        "完成", "全部", "整体", "完整", "综合",
    }
    
    COMPLEXITY_INDICATORS = {
        "complex": [
            "architecture", "system", "pipeline", "workflow", "framework",
            "multiple", "several", "various", "comprehensive", "end-to-end",
            "full-stack", "microservice", "distributed", "scalable",
            "架构", "系统", "流程", "框架", "多个", "全面", "分布式",
            "复杂的", "完整的", "整个", "全部", "综合",
            "项目", "应用", "服务", "模块", "组件",
        ],
        "conditional": [
            "if", "when", "unless", "depending on", "based on",
            "according to", "in case", "otherwise", "alternatively",
            "如果", "当", "根据", "否则", "或者", "条件",
            "需要判断", "需要检查", "需要验证",
        ],
        "iteration": [
            "for each", "loop", "iterate", "repeat", "batch",
            "all files", "every", "multiple times",
            "每个", "循环", "重复", "批量", "所有文件", "多次",
            "遍历", "逐个", "依次", "全部",
        ],
    }
    
    def __init__(
        self,
        complexity_threshold: float = 0.35,
        min_steps_for_planning: int = 2,
        max_steps_estimate: int = 10,
        provider: "LLMProvider | None" = None,
    ):
        self._complexity_threshold = complexity_threshold
        self._min_steps_for_planning = min_steps_for_planning
        self._max_steps_estimate = max_steps_estimate
        self._provider = provider
    
    def set_provider(self, provider: "LLMProvider") -> None:
        """Set the LLM provider for intelligent analysis."""
        self._provider = provider
    
    def analyze(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        use_llm: bool = True,
    ) -> ComplexityAnalysis:
        """
        Analyze task complexity with three-stage approach.
        
        Args:
            task: The task description
            context: Optional context (history, available tools, etc.)
            use_llm: Whether to use LLM for uncertain cases
        
        Returns:
            ComplexityAnalysis with level, score, and recommendations
        """
        task_lower = task.lower().strip()
        
        pre_screen = self._quick_pre_screen(task_lower)

        # For /plan command, always use LLM to determine plan_type
        # This ensures semantic understanding rather than keyword matching
        if use_llm and self._provider:
            llm_analysis = self._analyze_with_llm(task, context)
            if llm_analysis:
                # Override pre_screen results with LLM's plan_type judgment
                if pre_screen == "simple":
                    llm_analysis.needs_planning = False
                    llm_analysis.suggested_mode = "direct"
                elif pre_screen == "complex":
                    llm_analysis.needs_planning = True
                    llm_analysis.suggested_mode = "planning"
                return llm_analysis

        # Fallback to rule-based plan_type detection
        plan_type = self._detect_plan_type(task, task_lower)

        if pre_screen == "simple":
            return ComplexityAnalysis(
                level=ComplexityLevel.SIMPLE,
                score=0.1,
                reasons=["Quick pre-screen: clearly a simple task"],
                suggested_mode="direct",
                needs_planning=False,
                estimated_steps=1,
                plan_type=plan_type,
            )
        elif pre_screen == "complex":
            return ComplexityAnalysis(
                level=ComplexityLevel.COMPLEX,
                score=0.8,
                reasons=["Quick pre-screen: clearly a complex task"],
                suggested_mode="planning",
                needs_planning=True,
                estimated_steps=5,
                plan_type=plan_type,
            )

        rule_analysis = self._rule_based_analysis(task, task_lower)

        if rule_analysis["score"] < 0.3 or rule_analysis["score"] > 0.7:
            needs_planning = rule_analysis["score"] >= self._complexity_threshold
            return ComplexityAnalysis(
                level=self._determine_level(rule_analysis["score"]),
                score=rule_analysis["score"],
                reasons=rule_analysis["reasons"],
                suggested_mode="planning" if needs_planning else "direct",
                needs_planning=needs_planning,
                estimated_steps=rule_analysis["estimated_steps"],
                plan_type=plan_type,
            )
        
        needs_planning = rule_analysis["score"] >= self._complexity_threshold
        return ComplexityAnalysis(
            level=self._determine_level(rule_analysis["score"]),
            score=rule_analysis["score"],
            reasons=rule_analysis["reasons"] + ["Used rule-based fallback (LLM unavailable)"],
            suggested_mode="planning" if needs_planning else "direct",
            needs_planning=needs_planning,
            estimated_steps=rule_analysis["estimated_steps"],
            plan_type=plan_type,
        )
    
    def _quick_pre_screen(self, task_lower: str) -> str:
        """
        Quick pre-screening to identify clearly simple or complex tasks.
        Returns: "simple", "complex", or "uncertain"
        """
        # First check for complex patterns to avoid false simple classification
        for pattern in self.CLEARLY_COMPLEX_PATTERNS:
            if pattern in task_lower:
                return "complex"
        
        # Check for multi-step keywords that indicate complexity
        for keyword in self.MULTI_STEP_KEYWORDS:
            if keyword in task_lower:
                return "uncertain"  # Let rule-based analysis handle it
        
        # Check for analysis-related tasks that are likely complex
        analysis_keywords = ["分析", "analyze", "analysis", "评估", "evaluate", "assessment"]
        for keyword in analysis_keywords:
            if keyword in task_lower:
                return "uncertain"  # Let rule-based analysis handle it
        
        # Check for simple starts
        for pattern in self.CLEARLY_SIMPLE_STARTS:
            if task_lower.startswith(pattern):
                return "simple"
        
        # Check for simple patterns with word count limit
        for pattern in self.CLEARLY_SIMPLE_PATTERNS:
            if pattern in task_lower:
                word_count = len(task_lower.split())
                if word_count < 15:
                    return "simple"
        
        return "uncertain"
    
    def _rule_based_analysis(self, task: str, task_lower: str) -> dict[str, Any]:
        """Perform rule-based complexity analysis."""
        score = 0.0
        reasons = []
        
        # Check for analysis-related tasks
        analysis_keywords = ["分析", "analyze", "analysis", "评估", "evaluate", "assessment"]
        for keyword in analysis_keywords:
            if keyword in task_lower:
                score += 0.4
                reasons.append("Contains analysis requirements")
                break
        
        multi_step_score = self._check_multi_step_keywords(task_lower)
        if multi_step_score > 0:
            score += multi_step_score * 0.3
            reasons.append("Contains multi-step indicators")
        
        complexity_score = self._check_complexity_indicators(task_lower)
        if complexity_score > 0:
            score += complexity_score * 0.25
            reasons.append("Contains complexity indicators")
        
        conditional_score = self._check_conditional_indicators(task_lower)
        if conditional_score > 0:
            score += conditional_score * 0.2
            reasons.append("Contains conditional logic")
        
        iteration_score = self._check_iteration_indicators(task_lower)
        if iteration_score > 0:
            score += iteration_score * 0.15
            reasons.append("Contains iteration/loop patterns")
        
        length_score = self._check_task_length(task)
        score += length_score * 0.1
        if length_score > 0.5:
            reasons.append("Task description is lengthy")
        
        sentence_count = len(re.split(r'[.!?。！？]+', task))
        if sentence_count > 3:
            score += 0.1
            reasons.append(f"Contains {sentence_count} sentences")
        
        score = max(0.0, min(1.0, score))
        estimated_steps = self._estimate_steps(task_lower, score)
        
        return {
            "score": score,
            "reasons": reasons,
            "estimated_steps": estimated_steps,
        }
    
    def _analyze_with_llm(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> ComplexityAnalysis | None:
        """Use LLM to analyze task complexity."""
        if not self._provider:
            return None
        
        try:
            tools = context.get("tools", []) if context else []
            tools_str = ", ".join(tools[:20]) if tools else "general tools"
            
            prompt = COMPLEXITY_ANALYSIS_PROMPT.format(
                task=task,
                tools=tools_str,
            )
            
            response = self._provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300,
            )
            
            content = response.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
            
            result = json.loads(content)
            
            level_map = {
                "simple": ComplexityLevel.SIMPLE,
                "moderate": ComplexityLevel.MODERATE,
                "complex": ComplexityLevel.COMPLEX,
            }
            
            level = level_map.get(
                result.get("complexity_level", "moderate").lower(),
                ComplexityLevel.MODERATE,
            )
            
            return ComplexityAnalysis(
                level=level,
                score=result.get("confidence", 0.5),
                reasons=result.get("reasons", ["LLM analysis"]),
                suggested_mode="planning" if result.get("needs_planning", False) else "direct",
                needs_planning=result.get("needs_planning", False),
                estimated_steps=min(10, max(1, result.get("estimated_steps", 3))),
                plan_type=result.get("plan_type", "actionable"),
            )
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"LLM complexity analysis failed: {e}")
            return None
    
    def _check_multi_step_keywords(self, task: str) -> float:
        """Check for multi-step keywords."""
        matches = sum(1 for kw in self.MULTI_STEP_KEYWORDS if kw in task)
        return min(1.0, matches * 0.25)
    
    def _check_complexity_indicators(self, task: str) -> float:
        """Check for complexity indicators."""
        matches = sum(1 for kw in self.COMPLEXITY_INDICATORS["complex"] if kw in task)
        return min(1.0, matches * 0.2)
    
    def _check_conditional_indicators(self, task: str) -> float:
        """Check for conditional logic indicators."""
        matches = sum(1 for kw in self.COMPLEXITY_INDICATORS["conditional"] if kw in task)
        return min(1.0, matches * 0.25)
    
    def _check_iteration_indicators(self, task: str) -> float:
        """Check for iteration/loop indicators."""
        matches = sum(1 for kw in self.COMPLEXITY_INDICATORS["iteration"] if kw in task)
        return min(1.0, matches * 0.3)
    
    def _check_task_length(self, task: str) -> float:
        """Check task length as a complexity factor."""
        word_count = len(task.split())
        if word_count < 10:
            return 0.0
        elif word_count < 30:
            return 0.3
        elif word_count < 50:
            return 0.5
        else:
            return 0.8
    
    def _determine_level(self, score: float) -> ComplexityLevel:
        """Determine complexity level from score."""
        if score < 0.25:
            return ComplexityLevel.SIMPLE
        elif score < 0.5:
            return ComplexityLevel.MODERATE
        else:
            return ComplexityLevel.COMPLEX
    
    def _estimate_steps(self, task: str, score: float) -> int:
        """Estimate number of steps needed."""
        base_steps = 1
        
        action_verbs = re.findall(
            r'\b(create|build|write|implement|configure|set up|deploy|'
            r'refactor|migrate|integrate|test|fix|update|add|remove|delete)\b',
            task
        )
        base_steps += len(action_verbs)
        
        chinese_verbs = re.findall(
            r'(创建|构建|编写|实现|配置|部署|重构|迁移|集成|测试|修复|更新|添加|删除|运行|执行)',
            task
        )
        base_steps += len(chinese_verbs)
        
        if "and" in task:
            base_steps += task.count(" and ")
        if "then" in task:
            base_steps += task.count(" then ")
        
        chinese_connectors = ['然后', '接着', '之后', '最后', '并且', '同时']
        for connector in chinese_connectors:
            if connector in task:
                base_steps += task.count(connector)
        
        estimated = int(base_steps * (1 + score))
        
        return min(self._max_steps_estimate, max(1, estimated))

    def _detect_plan_type(self, task: str, task_lower: str) -> str:
        """Detect if the plan is informational or actionable.

        Returns: "informational" or "actionable"
        """
        # First check for action verbs that indicate actionable plans
        # This takes priority to avoid misclassifying development tasks
        action_patterns = [
            r'\b(create|build|write|implement|configure|set up|deploy|'
            r'refactor|migrate|integrate|test|fix|update|add|remove|delete|'
            r'generate|make|setup|install|run|execute|develop)\b',
            r'(创建|构建|编写|实现|配置|部署|重构|迁移|集成|测试|修复|'
            r'更新|添加|删除|运行|执行|生成|制作|设置|安装|开发)',
        ]

        for pattern in action_patterns:
            if re.search(pattern, task_lower):
                return "actionable"

        # Check for development/technical keywords that indicate actionable plans
        technical_patterns = [
            r'(小程序|app|应用|系统|服务|项目|网站|接口|api|数据库|前端|后端|框架)',
            r'(微信|支付宝|抖音|快手|淘宝)',
            r'(功能|模块|组件|页面|架构)',
        ]

        for pattern in technical_patterns:
            if re.search(pattern, task_lower):
                return "actionable"

        # Then check for informational patterns (advice, suggestions)
        # These are typically about life, travel, learning, etc.
        informational_patterns = [
            "假期", "旅行", "旅游", "行程", "攻略",
            "vacation", "travel", "trip", "itinerary",
            "如何安排", "怎么安排", "给点建议", "有什么建议",
            "学习建议", "职业规划", "生活建议",
        ]

        for pattern in informational_patterns:
            if pattern in task_lower:
                return "informational"

        # Default to actionable if uncertain
        return "actionable"

    def should_use_planning(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        use_llm: bool = True,
    ) -> bool:
        """Check if planning mode should be used."""
        analysis = self.analyze(task, context, use_llm=use_llm)
        return analysis.needs_planning
