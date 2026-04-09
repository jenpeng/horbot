"""Planning strategy interfaces for extensible plan generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from horbot.agent.planner.models import Plan, PlanStep


class StrategyType(Enum):
    """Types of planning strategies."""
    LLM_BASED = "llm_based"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"
    TEMPLATE_BASED = "template_based"


@dataclass
class StrategyContext:
    """Context passed to planning strategies."""
    task: str
    available_tools: list[str] = field(default_factory=list)
    max_steps: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)
    complexity_score: float = 0.0
    estimated_steps: int = 1


@dataclass
class StrategyResult:
    """Result from a planning strategy."""
    success: bool
    plan: Plan | None = None
    error: str | None = None
    confidence: float = 1.0
    strategy_used: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class PlanningStrategy(ABC):
    """
    Abstract base class for planning strategies.
    
    Planning strategies define how to generate execution plans from tasks.
    Different strategies can be used for different types of tasks or contexts.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for identification."""
        pass
    
    @property
    @abstractmethod
    def strategy_type(self) -> StrategyType:
        """Type of this strategy."""
        pass
    
    @property
    def priority(self) -> int:
        """Priority for strategy selection (higher = more preferred)."""
        return 0
    
    @property
    def supported_complexity_range(self) -> tuple[float, float]:
        """Range of complexity scores this strategy handles well."""
        return (0.0, 1.0)
    
    @abstractmethod
    async def generate(
        self,
        context: StrategyContext,
        provider: Any = None,
    ) -> StrategyResult:
        """
        Generate a plan for the given context.
        
        Args:
            context: Planning context with task and constraints
            provider: Optional LLM provider for LLM-based strategies
        
        Returns:
            StrategyResult with the generated plan or error
        """
        pass
    
    def can_handle(self, context: StrategyContext) -> bool:
        """
        Check if this strategy can handle the given context.
        
        Args:
            context: Planning context to evaluate
        
        Returns:
            True if this strategy is suitable for the context
        """
        min_complexity, max_complexity = self.supported_complexity_range
        return min_complexity <= context.complexity_score <= max_complexity
    
    def estimate_confidence(self, context: StrategyContext) -> float:
        """
        Estimate confidence level for handling this context.
        
        Args:
            context: Planning context to evaluate
        
        Returns:
            Confidence level between 0.0 and 1.0
        """
        if not self.can_handle(context):
            return 0.0
        return 1.0


class LLMPlanningStrategy(PlanningStrategy):
    """
    LLM-based planning strategy.
    
    Uses an LLM to generate execution plans. Best for complex tasks
    that require reasoning and understanding.
    """
    
    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ):
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
    
    @property
    def name(self) -> str:
        return "llm_planning"
    
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.LLM_BASED
    
    @property
    def priority(self) -> int:
        return 100
    
    @property
    def supported_complexity_range(self) -> tuple[float, float]:
        return (0.3, 1.0)
    
    async def generate(
        self,
        context: StrategyContext,
        provider: Any = None,
    ) -> StrategyResult:
        if provider is None:
            return StrategyResult(
                success=False,
                error="LLM strategy requires a provider",
                strategy_used=self.name,
            )
        
        pass


class RuleBasedPlanningStrategy(PlanningStrategy):
    """
    Rule-based planning strategy.
    
    Uses pattern matching and rules to generate simple plans.
    Best for straightforward, well-structured tasks.
    """
    
    def __init__(self):
        self._rules: list[tuple[Callable[[str], bool], Callable[[str], list[PlanStep]]]] = []
        self._register_default_rules()
    
    @property
    def name(self) -> str:
        return "rule_based"
    
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.RULE_BASED
    
    @property
    def priority(self) -> int:
        return 50
    
    @property
    def supported_complexity_range(self) -> tuple[float, float]:
        return (0.0, 0.5)
    
    def _register_default_rules(self) -> None:
        pass
    
    def register_rule(
        self,
        condition: Callable[[str], bool],
        generator: Callable[[str], list[PlanStep]],
    ) -> None:
        """
        Register a custom planning rule.
        
        Args:
            condition: Function that checks if rule applies
            generator: Function that generates steps when rule applies
        """
        self._rules.append((condition, generator))
    
    async def generate(
        self,
        context: StrategyContext,
        provider: Any = None,
    ) -> StrategyResult:
        import re
        import uuid
        
        steps: list[PlanStep] = []
        step_id = 1
        
        action_patterns = [
            (r'\b(read|show|display|list)\s+(\S+)', 'read_file', 'path'),
            (r'\b(write|create|save)\s+(\S+)', 'write_file', 'path'),
            (r'\b(edit|modify|update)\s+(\S+)', 'edit_file', 'path'),
            (r'\b(run|execute|call)\s+(.+)', 'exec', 'command'),
            (r'\b(search|find|look\s+for)\s+(.+)', 'web_search', 'query'),
            (r'\b(fetch|get|download)\s+(.+)', 'web_fetch', 'url'),
        ]
        
        task_lower = context.task.lower()
        for pattern, tool, param in action_patterns:
            matches = re.findall(pattern, task_lower)
            for match in matches:
                steps.append(PlanStep(
                    id=f"step_{step_id}",
                    description=f"{match[0]} {match[1]}",
                    tool_name=tool,
                    parameters={param: match[1]},
                    dependencies=[f"step_{step_id-1}"] if step_id > 1 else [],
                ))
                step_id += 1
        
        if not steps:
            steps.append(PlanStep(
                id="step_1",
                description=context.task,
                tool_name=None,
                parameters={},
            ))
        
        plan = Plan(
            id=str(uuid.uuid4())[:8],
            title=f"Plan: {context.task[:50]}...",
            description=context.task,
            steps=steps,
        )
        
        return StrategyResult(
            success=True,
            plan=plan,
            confidence=0.7,
            strategy_used=self.name,
        )


class HybridPlanningStrategy(PlanningStrategy):
    """
    Hybrid planning strategy.
    
    Combines rule-based and LLM-based approaches for optimal results.
    Uses rules for simple patterns and LLM for complex reasoning.
    """
    
    def __init__(
        self,
        rule_strategy: RuleBasedPlanningStrategy | None = None,
        llm_strategy: LLMPlanningStrategy | None = None,
    ):
        self._rule_strategy = rule_strategy or RuleBasedPlanningStrategy()
        self._llm_strategy = llm_strategy or LLMPlanningStrategy()
    
    @property
    def name(self) -> str:
        return "hybrid"
    
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.HYBRID
    
    @property
    def priority(self) -> int:
        return 80
    
    @property
    def supported_complexity_range(self) -> tuple[float, float]:
        return (0.0, 1.0)
    
    async def generate(
        self,
        context: StrategyContext,
        provider: Any = None,
    ) -> StrategyResult:
        if context.complexity_score < 0.3:
            return await self._rule_strategy.generate(context, provider)
        
        if context.complexity_score >= 0.3 and provider is not None:
            return await self._llm_strategy.generate(context, provider)
        
        return await self._rule_strategy.generate(context, provider)


class StrategyRegistry:
    """
    Registry for planning strategies.
    
    Manages available strategies and selects the best one for a given context.
    """
    
    def __init__(self):
        self._strategies: dict[str, PlanningStrategy] = {}
        self._register_defaults()
    
    def _register_defaults(self) -> None:
        self.register(RuleBasedPlanningStrategy())
        self.register(LLMPlanningStrategy())
        self.register(HybridPlanningStrategy())
    
    def register(self, strategy: PlanningStrategy) -> None:
        """
        Register a planning strategy.
        
        Args:
            strategy: Strategy to register
        """
        self._strategies[strategy.name] = strategy
    
    def get(self, name: str) -> PlanningStrategy | None:
        """Get a strategy by name."""
        return self._strategies.get(name)
    
    def get_all(self) -> list[PlanningStrategy]:
        """Get all registered strategies."""
        return list(self._strategies.values())
    
    def select_best(self, context: StrategyContext) -> PlanningStrategy | None:
        """
        Select the best strategy for a given context.
        
        Args:
            context: Planning context
        
        Returns:
            Best matching strategy or None if no suitable strategy found
        """
        candidates = [
            (s, s.estimate_confidence(context))
            for s in self._strategies.values()
            if s.can_handle(context)
        ]
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: (x[1], x[0].priority), reverse=True)
        return candidates[0][0]
    
    def select_by_type(self, strategy_type: StrategyType) -> PlanningStrategy | None:
        """
        Select a strategy by type.
        
        Args:
            strategy_type: Type of strategy to select
        
        Returns:
            First matching strategy or None
        """
        for strategy in self._strategies.values():
            if strategy.strategy_type == strategy_type:
                return strategy
        return None
