"""Plan generator using LLM for creating execution plans."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, Callable, Awaitable
import uuid

from horbot.agent.planner.models import Plan, PlanStep, PlanStatus, PlanSpec, PlanChecklist, PlanChecklistItem
from horbot.agent.planner.analyzer import TaskAnalyzer
from horbot.agent.planner.strategy import (
    StrategyRegistry,
    StrategyContext,
    StrategyResult,
    PlanningStrategy,
    StrategyType,
)
from horbot.agent.planner.errors import (
    PlanGenerationError,
    PlanParseError,
    PlannerError,
    ErrorRecovery,
)


PLAN_GENERATION_PROMPT = """You are a task planning assistant. Your job is to create a detailed execution plan based on the task description.

## IMPORTANT - DO NOT EXECUTE TOOLS
You are in PLANNING MODE. Do NOT execute any tools or commands. Only create a written plan.
Do NOT use read_file, write_file, edit_file, exec, or any other tools.
Your response must be a JSON plan only - no tool calls, no actions, just the plan.

## Task
{task}

## Available Tools (for reference only - do NOT execute)
{tools}

## Constraints
- Maximum {max_steps} steps
- Each step should be atomic and achievable with available tools
- Identify dependencies between steps
- Mark steps that can run in parallel

## Output Format
Return ONLY a JSON object with this structure (no other text, no tool calls):
```json
{{
  "title": "Plan title (简洁的中文名称，如'项目架构重构')",
  "description": "Brief description of the plan",
  "spec": {{
    "why": "Explain why this plan is needed and what problem it solves",
    "what_changes": [
      "List of changes that will be made",
      "Each change should be specific and actionable"
    ],
    "impact": {{
      "affected_specs": ["List of affected specifications"],
      "affected_code": ["List of affected code files or modules"]
    }},
    "added_requirements": [
      {{
        "name": "Requirement name",
        "description": "Detailed description of the new requirement",
        "scenarios": [
          {{
            "name": "Scenario name",
            "steps": [
              "WHEN condition or action",
              "THEN expected result",
              "AND additional result"
            ]
          }}
        ]
      }}
    ],
    "modified_requirements": [
      {{
        "name": "Requirement name",
        "description": "Detailed description of the modified requirement",
        "scenarios": [
          {{
            "name": "Scenario name",
            "steps": [
              "WHEN condition or action",
              "THEN expected result",
              "AND additional result"
            ]
          }}
        ]
      }}
    ],
    "removed_requirements": [
      {{
        "name": "Requirement name",
        "description": "Detailed description of the removed requirement",
        "scenarios": [
          {{
            "name": "Scenario name",
            "steps": [
              "WHEN condition or action",
              "THEN expected result",
              "AND additional result"
            ]
          }}
        ]
      }}
    ]
  }},
  "steps": [
    {{
      "id": "step_1",
      "description": "What this step does",
      "tool_name": "tool_to_use",
      "parameters": {{
        "param1": "value1",
        "param2": "value2"
      }},
      "dependencies": []
    }}
  ],
  "checklist": [
    {{
      "id": "check_1",
      "description": "Verification checkpoint description",
      "category": "implementation|testing|validation"
    }}
  ]
}}
```

## Rules
1. Step IDs should be unique (e.g., "step_1", "step_2")
2. Dependencies should reference step IDs
3. Steps with no dependencies can run in parallel
4. Only use tools from the available tools list
5. Keep descriptions concise but clear
6. The spec section should explain the rationale and impact
7. The checklist should include verification points for each major step
8. REMEMBER: Do NOT execute any tools - only create the plan JSON
9. The title should be a concise Chinese name suitable for use as a folder name (e.g., "项目架构重构", "代码优化", "功能开发")
10. Each requirement MUST include at least one scenario with WHEN/THEN/AND steps
11. Scenarios should describe concrete test cases or usage examples
12. Use WHEN for preconditions or actions, THEN for expected results, AND for additional results

## IMPORTANT - Parameters Guidelines
13. For each step, you MUST provide complete and specific parameters for the tool
14. Common parameters examples:
    - For file operations: {{"path": "/path/to/file", "content": "file content"}}
    - For Excel operations: {{"filepath": "/path/to/file.xlsx", "sheet_name": "Sheet1"}}
    - For Word operations: {{"filename": "/path/to/file.docx"}}
    - For PowerPoint operations: {{"filepath": "/path/to/file.pptx"}}
    - For web search: {{"query": "search query"}}
    - For exec: {{"command": "shell command"}}
15. Use absolute paths starting with workspace directory when possible
16. Generate meaningful file names based on the task context
17. If a tool requires a file path, always provide a specific path, not a placeholder

Generate the plan now:"""


SPEC_GENERATION_PROMPT = """You are a task planning assistant. Your job is to create the SPECIFICATION part of an execution plan.

## IMPORTANT - DO NOT EXECUTE TOOLS
You are in PLANNING MODE. Do NOT execute any tools or commands. Only create the spec document.
Do NOT use read_file, write_file, edit_file, exec, or any other tools.
Your response must be a JSON spec only - no tool calls, no actions, just the spec.

## Task
{task}

## Constraints
- Focus ONLY on the specification (why, what changes, impact, requirements)
- Do NOT include steps or checklist in this response
- Be specific and actionable

## Output Format
Return ONLY a JSON object with this structure (no other text, no tool calls):
```json
{{
  "title": "Plan title (简洁的中文名称，如'项目架构重构')",
  "description": "Brief description of the plan",
  "spec": {{
    "why": "Explain why this plan is needed and what problem it solves",
    "what_changes": [
      "List of changes that will be made",
      "Each change should be specific and actionable"
    ],
    "impact": {{
      "affected_specs": ["List of affected specifications"],
      "affected_code": ["List of affected code files or modules"]
    }},
    "added_requirements": [
      {{
        "name": "Requirement name",
        "description": "Detailed description of the new requirement",
        "scenarios": [
          {{
            "name": "Scenario name",
            "steps": [
              "WHEN condition or action",
              "THEN expected result",
              "AND additional result"
            ]
          }}
        ]
      }}
    ],
    "modified_requirements": [
      {{
        "name": "Requirement name",
        "description": "Detailed description of the modified requirement",
        "scenarios": [
          {{
            "name": "Scenario name",
            "steps": [
              "WHEN condition or action",
              "THEN expected result",
              "AND additional result"
            ]
          }}
        ]
      }}
    ],
    "removed_requirements": [
      {{
        "name": "Requirement name",
        "description": "Detailed description of the removed requirement",
        "scenarios": [
          {{
            "name": "Scenario name",
            "steps": [
              "WHEN condition or action",
              "THEN expected result",
              "AND additional result"
            ]
          }}
        ]
      }}
    ]
  }}
}}
```

## Rules
1. The title should be a concise Chinese name suitable for use as a folder name
2. Each requirement MUST include at least one scenario with WHEN/THEN/AND steps
3. Scenarios should describe concrete test cases or usage examples
4. Use WHEN for preconditions or actions, THEN for expected results, AND for additional results
5. REMEMBER: Do NOT execute any tools - only create the spec JSON

Generate the spec now:"""


TASKS_GENERATION_PROMPT = """You are a task planning assistant. Your job is to create the TASKS part of an execution plan based on the spec.

## CRITICAL - DO NOT EXECUTE ANY TOOLS
You are in PLANNING MODE ONLY. You MUST NOT execute any tools or commands.
- Do NOT call read_file, write_file, edit_file, exec, or any other tools
- Do NOT generate tool call syntax like: tool_name(parameters)
- Do NOT include any "parameters" fields in your response
- Your response must be ONLY a JSON object with the tasks list
- NO tool calls, NO actions, NO code execution - JUST the JSON tasks list

## Original Task
{task}

## Spec (Already Generated)
{spec}

## Available Tools (for reference only - do NOT execute)
{tools}

## Available Skills (for reference only)
{skills}

## Available MCP Tools (for reference only)
{mcp_tools}

## Constraints
- Maximum {max_steps} steps
- Each step should be atomic and achievable with available tools
- Identify dependencies between steps
- Mark steps that can run in parallel
- Identify which skills and MCP tools are needed for each step

## Output Format
Return ONLY a JSON object with this structure (no other text, no tool calls):
```json
{{
  "steps": [
    {{
      "id": "step_1",
      "description": "步骤描述（请用中文）",
      "tool_name": "tool_to_use",
      "parameters": {{
        "param1": "value1",
        "param2": "value2"
      }},
      "dependencies": [],
      "required_skills": ["skill_name_1", "skill_name_2"],
      "required_mcp_tools": ["mcp_server_tool_name"]
    }}
  ]
}}
```

## Rules
1. Step IDs should be unique (e.g., "step_1", "step_2")
2. Dependencies should reference step IDs
3. Steps with no dependencies can run in parallel
4. Only use tools from the available tools list
5. Keep descriptions concise but clear
6. IMPORTANT: All descriptions MUST be in Chinese (中文)
7. REMEMBER: Do NOT execute any tools - only create the tasks JSON

## Skills and MCP Tools Guidelines
7. required_skills: List of skill names that provide guidance for this step
   - Use skills that contain relevant patterns, templates, or best practices
   - Example: ["coding-standards", "react-patterns", "api-design"]
8. required_mcp_tools: List of MCP tool names needed for this step
   - MCP tools are named as: mcp_{{server}}_{{tool}}
   - Example: ["mcp_browser_navigate", "mcp_excel_write_data"]
   - Leave empty if no MCP tools are needed

## IMPORTANT - Parameters Guidelines
9. For each step, you MUST provide complete and specific parameters for the tool
10. Common parameters examples:
    - For file operations: {{"path": "/path/to/file", "content": "file content"}}
    - For Excel operations: {{"filepath": "/path/to/file.xlsx", "sheet_name": "Sheet1"}}
    - For Word operations: {{"filename": "/path/to/file.docx"}}
    - For PowerPoint operations: {{"filepath": "/path/to/file.pptx"}}
    - For web search: {{"query": "search query"}}
    - For exec: {{"command": "shell command"}}
11. Use absolute paths starting with workspace directory when possible
12. Generate meaningful file names based on the task context
13. If a tool requires a file path, always provide a specific path, not a placeholder

Generate the tasks now:"""


CHECKLIST_GENERATION_PROMPT = """You are a task planning assistant. Your job is to create the CHECKLIST part of an execution plan based on the spec and tasks.

## IMPORTANT - DO NOT EXECUTE TOOLS
You are in PLANNING MODE. Do NOT execute any tools or commands. Only create the checklist document.
Do NOT use read_file, write_file, edit_file, exec, or any other tools.
Your response must be a JSON checklist only - no tool calls, no actions, just the checklist.

## Original Task
{task}

## Spec (Already Generated)
{spec}

## Tasks (Already Generated)
{tasks}

## Output Format
Return ONLY a JSON object with this structure (no other text, no tool calls):
```json
{{
  "checklist": [
    {{
      "id": "check_1",
      "description": "验收检查点描述（请用中文）",
      "category": "implementation|testing|validation"
    }}
  ]
}}
```

## Rules
1. Checklist IDs should be unique (e.g., "check_1", "check_2")
2. Categories should be one of: implementation, testing, validation
3. Each major step should have at least one verification checkpoint
4. Include checkpoints for:
   - Implementation: Code/functionality implementation checks
   - Testing: Unit tests, integration tests
   - Validation: User acceptance, edge cases
5. IMPORTANT: All descriptions MUST be in Chinese (中文)
6. REMEMBER: Do NOT execute any tools - only create the checklist JSON

Generate the checklist now (in Chinese):"""


class LLMProvider(Protocol):
    """Protocol for LLM provider interface."""
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Any:
        ...


@dataclass
class GenerationConfig:
    """Configuration for plan generation."""
    max_steps: int = 10
    temperature: float = 0.3
    max_tokens: int = 8000
    model: str | None = None
    fallback_to_rules: bool = True
    validate_output: bool = True


@dataclass
class GenerationResult:
    """Result of plan generation."""
    success: bool
    plan: Plan | None = None
    error: str | None = None
    raw_response: str | None = None
    spec_content: str | None = None
    tasks_content: str | None = None
    checklist_content: str | None = None
    strategy_used: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "plan": self.plan.to_dict() if self.plan else None,
            "error": self.error,
            "strategy_used": self.strategy_used,
            "confidence": self.confidence,
        }


class PlanGenerator:
    """
    Generates execution plans using LLM or rule-based strategies.
    
    The generator:
    1. Takes a task description
    2. Analyzes complexity to select appropriate strategy
    3. Uses the strategy to generate a plan
    4. Parses and validates the response
    5. Returns a structured Plan object with spec, tasks, and checklist documents
    
    Supports:
    - LLM-based planning for complex tasks
    - Rule-based planning for simple tasks
    - Hybrid approach combining both
    - Custom planning strategies
    """
    
    def __init__(
        self,
        provider: LLMProvider | None = None,
        model: str | None = None,
        planning_model: str | None = None,
        planning_provider: LLMProvider | None = None,
        max_steps: int = 10,
        analyzer: TaskAnalyzer | None = None,
        config: GenerationConfig | None = None,
        strategy_registry: StrategyRegistry | None = None,
    ):
        self._provider = provider
        self._model = model
        self._planning_model = planning_model
        self._planning_provider = planning_provider
        self._max_steps = max_steps
        self._analyzer = analyzer or TaskAnalyzer()
        self._config = config or GenerationConfig(max_steps=max_steps, model=model)
        self._strategy_registry = strategy_registry or StrategyRegistry()
    
    @property
    def provider(self) -> LLMProvider | None:
        """Get the LLM provider."""
        return self._provider
    
    @provider.setter
    def provider(self, value: LLMProvider) -> None:
        """Set the LLM provider."""
        self._provider = value
    
    def register_strategy(self, strategy: PlanningStrategy) -> None:
        """
        Register a custom planning strategy.
        
        Args:
            strategy: Strategy to register
        """
        self._strategy_registry.register(strategy)
    
    async def generate(
        self,
        task: str,
        available_tools: list[str] | None = None,
        context: dict[str, Any] | None = None,
        strategy_name: str | None = None,
        session_id: str | None = None,
        on_progress: Callable[[str, str, str | None], Awaitable[None]] | None = None,
        available_skills: list[str] | None = None,
        available_mcp_tools: list[str] | None = None,
    ) -> GenerationResult:
        """
        Generate an execution plan for the given task.
        
        Args:
            task: The task description
            available_tools: List of available tool names
            context: Additional context for planning
            strategy_name: Optional specific strategy to use
            session_id: Optional session ID for token tracking
            on_progress: Optional callback for progress updates (step_name, step_type, content)
            available_skills: List of available skill names
            available_mcp_tools: List of available MCP tool names
        
        Returns:
            GenerationResult with the plan or error
        """
        if hasattr(self._analyzer, '_cache'):
            self._analyzer._cache.clear()
        
        analysis = self._analyzer.analyze(task, context)
        
        strategy_context = StrategyContext(
            task=task,
            available_tools=available_tools or [],
            max_steps=self._config.max_steps,
            metadata=context or {},
            complexity_score=analysis.score,
            estimated_steps=analysis.estimated_steps,
        )
        
        if strategy_name:
            strategy = self._strategy_registry.get(strategy_name)
            if not strategy:
                return GenerationResult(
                    success=False,
                    error=f"Strategy '{strategy_name}' not found",
                )
        else:
            strategy = self._strategy_registry.select_best(strategy_context)
        
        if not strategy:
            return GenerationResult(
                success=False,
                error="No suitable planning strategy found",
            )
        
        from loguru import logger
        logger.info("Selected strategy: {} (type: {})", strategy.name if hasattr(strategy, 'name') else strategy, strategy.strategy_type)
        
        try:
            if strategy.strategy_type == StrategyType.LLM_BASED:
                logger.info("Using LLM-based planning")
                return await self._generate_with_llm(
                    task=task,
                    available_tools=available_tools,
                    strategy_context=strategy_context,
                    session_id=session_id,
                    on_progress=on_progress,
                    available_skills=available_skills,
                    available_mcp_tools=available_mcp_tools,
                )
            elif strategy.strategy_type == StrategyType.RULE_BASED:
                logger.info("Using rule-based planning")
                return await self._generate_with_rules(
                    task=task,
                    strategy_context=strategy_context,
                )
            elif strategy.strategy_type == StrategyType.HYBRID:
                logger.info("Using hybrid planning - delegating to LLM")
                return await self._generate_with_llm(
                    task=task,
                    available_tools=available_tools,
                    strategy_context=strategy_context,
                    session_id=session_id,
                    on_progress=on_progress,
                    available_skills=available_skills,
                    available_mcp_tools=available_mcp_tools,
                )
            else:
                result = await strategy.generate(strategy_context, self._provider)
                return self._convert_strategy_result(result, task)
                
        except PlannerError as e:
            if self._config.fallback_to_rules:
                fallback_result = await self._generate_with_rules(
                    task=task,
                    strategy_context=strategy_context,
                )
                fallback_result.metadata["fallback_reason"] = str(e)
                return fallback_result
            
            return GenerationResult(
                success=False,
                error=str(e),
                metadata={"error_code": e.code.value, "details": e.details},
            )
        except Exception as e:
            import traceback
            from loguru import logger
            logger.error("Plan generation failed with exception: {} - {}\n{}", type(e).__name__, e, traceback.format_exc())
            return GenerationResult(
                success=False,
                error=str(e),
            )
    
    async def _generate_with_llm(
        self,
        task: str,
        available_tools: list[str] | None,
        strategy_context: StrategyContext,
        session_id: str | None = None,
        on_progress: Callable[[str, str, str | None], Awaitable[None]] | None = None,
        available_skills: list[str] | None = None,
        available_mcp_tools: list[str] | None = None,
    ) -> GenerationResult:
        """Generate plan using LLM with stepwise progress updates."""
        if not self._provider:
            raise PlanGenerationError("No LLM provider configured")
        
        tools_str = ", ".join(available_tools) if available_tools else "all available tools"
        skills_str = ", ".join(available_skills) if available_skills else "no specific skills"
        mcp_tools_str = ", ".join(available_mcp_tools) if available_mcp_tools else "no MCP tools"
        
        model_to_use = self._planning_model or self._config.model
        provider_to_use = self._planning_provider or self._provider
        
        from loguru import logger
        if self._planning_model:
            provider_name = getattr(provider_to_use, 'name', 'unknown') if provider_to_use else 'default'
            logger.info("Using planning model: {} with provider: {} (planning-specific)", 
                       self._planning_model, provider_name)
        else:
            logger.info("Using default model: {} (no planning model configured)", self._config.model)
        
        plan_title = "Execution Plan"
        plan_description = task
        spec_data = None
        steps_data = []
        checklist_data = []
        spec_content = ""
        tasks_content = ""
        checklist_content = ""
        
        # Step 1: Generate spec
        if on_progress:
            await on_progress("spec", "generating", None)
        
        spec_prompt = SPEC_GENERATION_PROMPT.format(task=task)
        spec_messages = [{"role": "user", "content": spec_prompt}]
        
        spec_response = await provider_to_use.chat(
            messages=spec_messages,
            tools=None,
            model=model_to_use,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        
        self._record_token_usage(spec_response, provider_to_use, model_to_use, session_id, logger)
        
        if spec_response.tool_calls:
            raise PlanGenerationError(
                "LLM attempted to use tools during spec generation",
                raw_response=spec_response.content or "",
            )
        
        spec_content_raw = spec_response.content or ""
        spec_data = self._parse_response(spec_content_raw)
        
        logger.info("Spec generation - raw response length: {}", len(spec_content_raw))
        logger.info("Spec generation - raw response preview: {}", spec_content_raw[:500] if spec_content_raw else "(empty)")
        logger.info("Spec generation - parsed spec_data: {}", spec_data)
        
        if spec_data:
            plan_title = spec_data.get("title", plan_title)
            plan_description = spec_data.get("description", plan_description)
            spec_content = self._generate_spec_md_from_data(spec_data, plan_title)
            logger.info("Spec generation - generated spec_content length: {}", len(spec_content))
            
            if on_progress:
                await on_progress("spec", "completed", spec_content)
        else:
            spec_content = f"# {plan_title} Spec\n\n## Why\n{task}"
            logger.warning("Spec generation - failed to parse spec_data, using fallback")
            if on_progress:
                await on_progress("spec", "completed", spec_content)
        
        # Step 2: Generate tasks
        if on_progress:
            await on_progress("tasks", "generating", None)
        
        spec_json_str = json.dumps(spec_data.get("spec", {}), ensure_ascii=False, indent=2) if spec_data else "{}"
        tasks_prompt = TASKS_GENERATION_PROMPT.format(
            task=task,
            spec=spec_json_str,
            tools=tools_str,
            skills=skills_str,
            mcp_tools=mcp_tools_str,
            max_steps=self._config.max_steps,
        )
        tasks_messages = [{"role": "user", "content": tasks_prompt}]
        
        tasks_response = await provider_to_use.chat(
            messages=tasks_messages,
            tools=None,
            model=model_to_use,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        
        self._record_token_usage(tasks_response, provider_to_use, model_to_use, session_id, logger)
        
        if tasks_response.tool_calls:
            raise PlanGenerationError(
                "LLM attempted to use tools during tasks generation",
                raw_response=tasks_response.content or "",
            )
        
        tasks_content_raw = tasks_response.content or ""
        tasks_data = self._parse_response(tasks_content_raw)
        
        logger.info("Tasks generation - raw response length: {}", len(tasks_content_raw))
        logger.info("Tasks generation - raw response preview: {}", tasks_content_raw[:500] if tasks_content_raw else "(empty)")
        logger.info("Tasks generation - parsed tasks_data: {}", tasks_data)
        
        if tasks_data:
            steps_data = tasks_data.get("steps", [])
            logger.info("Tasks generation - steps count: {}", len(steps_data))
        else:
            logger.warning("Tasks generation - failed to parse tasks_data, using empty steps")
        
        # Build partial plan for tasks content generation
        partial_plan = self._build_partial_plan(plan_title, plan_description, steps_data, spec_data)
        tasks_content = self._generate_tasks_md(partial_plan)
        
        logger.info("Tasks generation - generated tasks_content length: {}", len(tasks_content))
        
        if on_progress:
            await on_progress("tasks", "completed", tasks_content)
        
        # Step 3: Generate checklist
        if on_progress:
            await on_progress("checklist", "generating", None)
        
        tasks_json_str = json.dumps(steps_data, ensure_ascii=False, indent=2)
        checklist_prompt = CHECKLIST_GENERATION_PROMPT.format(
            task=task,
            spec=spec_json_str,
            tasks=tasks_json_str,
        )
        checklist_messages = [{"role": "user", "content": checklist_prompt}]
        
        checklist_response = await provider_to_use.chat(
            messages=checklist_messages,
            tools=None,
            model=model_to_use,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        
        self._record_token_usage(checklist_response, provider_to_use, model_to_use, session_id, logger)
        
        if checklist_response.tool_calls:
            raise PlanGenerationError(
                "LLM attempted to use tools during checklist generation",
                raw_response=checklist_response.content or "",
            )
        
        checklist_content_raw = checklist_response.content or ""
        checklist_data_parsed = self._parse_response(checklist_content_raw)
        
        if checklist_data_parsed:
            checklist_data = checklist_data_parsed.get("checklist", [])
        
        # Build final plan
        final_plan_data = {
            "title": plan_title,
            "description": plan_description,
            "spec": spec_data.get("spec", {}) if spec_data else {},
            "steps": steps_data,
            "checklist": checklist_data,
        }
        
        logger.debug("Final plan data - spec: {}", final_plan_data.get("spec", {}))
        logger.debug("Final plan data - steps count: {}", len(steps_data))
        
        plan = self._build_plan(final_plan_data, task)
        
        logger.debug("Built plan - spec.why: {}", plan.spec.why if plan.spec else "No spec")
        logger.debug("Built plan - spec.what_changes: {}", plan.spec.what_changes if plan.spec else [])
        
        if len(plan.steps) > self._config.max_steps:
            plan.steps = plan.steps[:self._config.max_steps]
        
        # Generate final content
        spec_content = self._generate_spec_md(plan, final_plan_data)
        checklist_content = self._generate_checklist_md(plan)
        
        if on_progress:
            await on_progress("checklist", "completed", checklist_content)
        
        return GenerationResult(
            success=True,
            plan=plan,
            raw_response=f"Spec:\n{spec_content_raw}\n\nTasks:\n{tasks_content_raw}\n\nChecklist:\n{checklist_content_raw}",
            spec_content=spec_content,
            tasks_content=tasks_content,
            checklist_content=checklist_content,
            strategy_used="llm_based",
            confidence=0.9,
        )
    
    def _record_token_usage(self, response, provider, model, session_id, logger):
        """Record token usage from LLM response."""
        if hasattr(response, 'usage') and response.usage:
            try:
                from horbot.agent.token_tracker import get_token_tracker
                tracker = get_token_tracker()
                provider_name = getattr(provider, 'name', 'unknown') if provider else 'default'
                tracker.record(
                    provider=provider_name,
                    model=model or "unknown",
                    prompt_tokens=response.usage.get("prompt_tokens", 0),
                    completion_tokens=response.usage.get("completion_tokens", 0),
                    total_tokens=response.usage.get("total_tokens", 0),
                    session_id=session_id,
                )
                logger.debug("Recorded planning token usage: prompt={}, completion={}", 
                             response.usage.get("prompt_tokens", 0),
                             response.usage.get("completion_tokens", 0))
            except Exception as e:
                logger.warning("Failed to record planning token usage: {}", e)
    
    def _generate_spec_md_from_data(self, spec_data: dict, title: str) -> str:
        """Generate spec.md content from parsed spec data."""
        spec = spec_data.get("spec", {})
        impact = spec.get("impact", {})
        
        lines = [
            f"# {title} Spec",
            "",
            "## Why",
            spec.get("why", ""),
            "",
            "## What Changes",
        ]
        
        for change in spec.get("what_changes", []):
            lines.append(f"- {change}")
        
        if not spec.get("what_changes"):
            lines.append("- 待规划具体变更内容")
        
        lines.extend([
            "",
            "## Impact",
            "- Affected specs: " + ", ".join(impact.get("affected_specs", [])) if impact.get("affected_specs") else "- Affected specs: 待确定",
            "- Affected code: " + ", ".join(impact.get("affected_code", [])) if impact.get("affected_code") else "- Affected code: 待确定",
        ])
        
        return "\n".join(lines)
    
    def _build_partial_plan(self, title: str, description: str, steps_data: list, spec_data: dict | None) -> Plan:
        """Build a partial Plan object for content generation."""
        steps = []
        for i, step_data in enumerate(steps_data):
            step = PlanStep(
                id=step_data.get("id", f"step_{i+1}"),
                description=step_data.get("description", ""),
                tool_name=step_data.get("tool_name"),
                parameters=step_data.get("parameters", {}),
                dependencies=step_data.get("dependencies", []),
                required_skills=step_data.get("required_skills", []),
                required_mcp_tools=step_data.get("required_mcp_tools", []),
            )
            steps.append(step)
        
        safe_title = self._sanitize_title(title)
        short_id = str(uuid.uuid4())[:8]
        plan_id = f"{safe_title}-{short_id}"
        
        return Plan(
            id=plan_id,
            title=title,
            description=description,
            steps=steps,
        )
    
    async def _generate_with_rules(
        self,
        task: str,
        strategy_context: StrategyContext,
    ) -> GenerationResult:
        """Generate plan using rule-based approach."""
        steps = []
        
        action_patterns = [
            (r'\b(read|show|display|list)\s+(\S+)', 'read_file', 'path'),
            (r'\b(write|create|save)\s+(\S+)', 'write_file', 'path'),
            (r'\b(edit|modify|update)\s+(\S+)', 'edit_file', 'path'),
            (r'\b(run|execute|call)\s+(.+)', 'exec', 'command'),
            (r'\b(search|find|look\s+for)\s+(.+)', 'web_search', 'query'),
            (r'\b(fetch|get|download)\s+(.+)', 'web_fetch', 'url'),
        ]
        
        step_id = 1
        for pattern, tool, param in action_patterns:
            matches = re.findall(pattern, task.lower())
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
                description=task,
                tool_name=None,
                parameters={},
            ))
        
        title = f"Plan: {task[:50]}..."
        safe_title = self._sanitize_title(title)
        short_id = str(uuid.uuid4())[:8]
        plan_id = f"{safe_title}-{short_id}"
        
        plan = Plan(
            id=plan_id,
            title=title,
            description=task,
            steps=steps,
        )
        
        default_scenarios = [
            {
                "name": "成功执行任务",
                "steps": [
                    "WHEN 用户提交任务请求",
                    "THEN 系统按计划执行步骤",
                    "AND 任务成功完成"
                ]
            },
            {
                "name": "任务执行失败",
                "steps": [
                    "WHEN 执行过程中遇到错误",
                    "THEN 系统报告错误信息",
                    "AND 提供错误恢复建议"
                ]
            }
        ]
        
        spec_content = self._generate_spec_md(plan, {
            "spec": {
                "why": f"解决用户提出的任务：{task}",
                "what_changes": ["待规划具体变更内容"],
                "impact": {},
                "added_requirements": [
                    {
                        "name": "任务执行功能",
                        "description": "系统应能够执行用户提交的任务",
                        "scenarios": default_scenarios
                    }
                ]
            }
        })
        tasks_content = self._generate_tasks_md(plan)
        checklist_content = self._generate_checklist_md(plan)
        
        return GenerationResult(
            success=True,
            plan=plan,
            spec_content=spec_content,
            tasks_content=tasks_content,
            checklist_content=checklist_content,
            strategy_used="rule_based",
            confidence=0.7,
        )
    
    def _convert_strategy_result(
        self,
        result: StrategyResult,
        original_task: str,
    ) -> GenerationResult:
        """Convert a StrategyResult to GenerationResult."""
        plan = result.plan
        
        spec_content = ""
        tasks_content = ""
        checklist_content = ""
        
        if plan:
            spec_content = self._generate_spec_md(plan, {"spec": {}})
            tasks_content = self._generate_tasks_md(plan)
            checklist_content = self._generate_checklist_md(plan)
        
        return GenerationResult(
            success=result.success,
            plan=plan,
            error=result.error,
            strategy_used=result.strategy_used,
            confidence=result.confidence,
            metadata=result.metadata,
            spec_content=spec_content,
            tasks_content=tasks_content,
            checklist_content=checklist_content,
        )
    
    def _parse_response(self, content: str) -> dict[str, Any] | None:
        """Parse LLM response to extract plan JSON."""
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, content)
            if match:
                json_str = match.group(1)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        
        brace_count = 0
        start_idx = -1
        for i, char in enumerate(content):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    json_str = content[start_idx:i+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        break
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        if start_idx != -1 and brace_count > 0:
            incomplete_json = content[start_idx:]
            from loguru import logger
            logger.warning("JSON appears to be truncated, attempting to fix: {} braces unclosed", brace_count)
            fixed_json = incomplete_json + '}' * brace_count
            try:
                return json.loads(fixed_json)
            except json.JSONDecodeError as e:
                logger.warning("Failed to fix truncated JSON: {}", e)
        
        return None
    
    def _sanitize_title(self, title: str) -> str:
        """
        Convert title to safe directory name.
        
        Args:
            title: The original title
            
        Returns:
            A safe directory name
        """
        safe_title = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', title)
        safe_title = re.sub(r'_+', '_', safe_title)
        safe_title = safe_title.strip('_')
        return safe_title[:50] if len(safe_title) > 50 else safe_title
    
    def _build_plan(self, data: dict[str, Any], original_task: str) -> Plan:
        """Build a Plan object from parsed data."""
        steps = []
        
        for i, step_data in enumerate(data.get("steps", [])):
            step = PlanStep(
                id=step_data.get("id", f"step_{i+1}"),
                description=step_data.get("description", ""),
                tool_name=step_data.get("tool_name"),
                parameters=step_data.get("parameters", {}),
                dependencies=step_data.get("dependencies", []),
                required_skills=step_data.get("required_skills", []),
                required_mcp_tools=step_data.get("required_mcp_tools", []),
            )
            steps.append(step)
        
        spec_data = data.get("spec", {})
        spec = PlanSpec(
            why=spec_data.get("why", ""),
            what_changes=spec_data.get("what_changes", []),
            impact=spec_data.get("impact", {}),
            added_requirements=spec_data.get("added_requirements", []),
            modified_requirements=spec_data.get("modified_requirements", []),
            removed_requirements=spec_data.get("removed_requirements", []),
        )
        
        checklist_data = data.get("checklist", [])
        checklist_items = [
            PlanChecklistItem(
                id=item.get("id", f"check_{i+1}"),
                description=item.get("description", ""),
                category=item.get("category", "implementation"),
                checked=False,
            )
            for i, item in enumerate(checklist_data)
        ]
        checklist = PlanChecklist(items=checklist_items)
        
        title = data.get("title", "Execution Plan")
        safe_title = self._sanitize_title(title)
        short_id = str(uuid.uuid4())[:8]
        plan_id = f"{safe_title}-{short_id}"
        
        return Plan(
            id=plan_id,
            title=title,
            description=data.get("description", original_task),
            steps=steps,
            spec=spec,
            checklist=checklist,
        )
    
    def _generate_spec_md(self, plan: Plan, plan_data: dict[str, Any]) -> str:
        """Generate spec.md content."""
        spec = plan.spec
        impact = spec.impact or {}
        
        lines = [
            f"# {plan.title} Spec",
            "",
            "## Why",
            spec.why or f"解决用户提出的任务：{plan.description}",
            "",
            "## What Changes",
        ]
        
        for change in spec.what_changes:
            lines.append(f"- {change}")
        
        if not spec.what_changes:
            lines.append("- 待规划具体变更内容")
        
        lines.extend([
            "",
            "## Impact",
            "- Affected specs: " + ", ".join(impact.get("affected_specs", [])) if impact.get("affected_specs") else "- Affected specs: 待确定",
            "- Affected code: " + ", ".join(impact.get("affected_code", [])) if impact.get("affected_code") else "- Affected code: 待确定",
            "",
            "## ADDED Requirements",
        ])
        
        if spec.added_requirements:
            for req in spec.added_requirements:
                name = req.get("name", "未命名需求") if isinstance(req, dict) else str(req)
                description = req.get("description", "") if isinstance(req, dict) else ""
                scenarios = req.get("scenarios", []) if isinstance(req, dict) else []
                lines.append(f"### Requirement: {name}")
                lines.append(description)
                lines.append("")
                for scenario in scenarios:
                    if isinstance(scenario, dict):
                        scenario_name = scenario.get("name", "未命名场景")
                        steps = scenario.get("steps", [])
                    else:
                        scenario_name = str(scenario)
                        steps = []
                    lines.append(f"#### Scenario: {scenario_name}")
                    for step in steps:
                        if isinstance(step, str):
                            if step.strip().upper().startswith("WHEN"):
                                lines.append(f"- **WHEN** {step[4:].strip()}")
                            elif step.strip().upper().startswith("THEN"):
                                lines.append(f"- **THEN** {step[4:].strip()}")
                            elif step.strip().upper().startswith("AND"):
                                lines.append(f"- **AND** {step[3:].strip()}")
                            else:
                                lines.append(f"- {step}")
                        else:
                            lines.append(f"- {step}")
                    lines.append("")
        else:
            lines.append("无新增需求")
            lines.append("")
        
        lines.append("## MODIFIED Requirements")
        
        if spec.modified_requirements:
            for req in spec.modified_requirements:
                name = req.get("name", "未命名需求") if isinstance(req, dict) else str(req)
                description = req.get("description", "") if isinstance(req, dict) else ""
                scenarios = req.get("scenarios", []) if isinstance(req, dict) else []
                lines.append(f"### Requirement: {name}")
                lines.append(description)
                lines.append("")
                for scenario in scenarios:
                    if isinstance(scenario, dict):
                        scenario_name = scenario.get("name", "未命名场景")
                        steps = scenario.get("steps", [])
                    else:
                        scenario_name = str(scenario)
                        steps = []
                    lines.append(f"#### Scenario: {scenario_name}")
                    for step in steps:
                        if isinstance(step, str):
                            if step.strip().upper().startswith("WHEN"):
                                lines.append(f"- **WHEN** {step[4:].strip()}")
                            elif step.strip().upper().startswith("THEN"):
                                lines.append(f"- **THEN** {step[4:].strip()}")
                            elif step.strip().upper().startswith("AND"):
                                lines.append(f"- **AND** {step[3:].strip()}")
                            else:
                                lines.append(f"- {step}")
                        else:
                            lines.append(f"- {step}")
                    lines.append("")
        else:
            lines.append("无修改需求")
            lines.append("")
        
        lines.append("## REMOVED Requirements")
        
        if spec.removed_requirements:
            for req in spec.removed_requirements:
                name = req.get("name", "未命名需求") if isinstance(req, dict) else str(req)
                description = req.get("description", "") if isinstance(req, dict) else ""
                scenarios = req.get("scenarios", []) if isinstance(req, dict) else []
                lines.append(f"### Requirement: {name}")
                lines.append(description)
                lines.append("")
                for scenario in scenarios:
                    if isinstance(scenario, dict):
                        scenario_name = scenario.get("name", "未命名场景")
                        steps = scenario.get("steps", [])
                    else:
                        scenario_name = str(scenario)
                        steps = []
                    lines.append(f"#### Scenario: {scenario_name}")
                    for step in steps:
                        if isinstance(step, str):
                            if step.strip().upper().startswith("WHEN"):
                                lines.append(f"- **WHEN** {step[4:].strip()}")
                            elif step.strip().upper().startswith("THEN"):
                                lines.append(f"- **THEN** {step[4:].strip()}")
                            elif step.strip().upper().startswith("AND"):
                                lines.append(f"- **AND** {step[3:].strip()}")
                            else:
                                lines.append(f"- {step}")
                        else:
                            lines.append(f"- {step}")
                    lines.append("")
        else:
            lines.append("无移除需求")
        
        return "\n".join(lines)
    
    def _generate_tasks_md(self, plan: Plan) -> str:
        """Generate tasks.md content."""
        lines = [
            f"# {plan.title} - 任务列表",
            "",
        ]
        
        for i, step in enumerate(plan.steps):
            status_marker = "[ ]" if step.status.value == "pending" else "[x]"
            lines.append(f"## {status_marker} 任务 {i+1}: {step.description}")
            lines.append(f"- **描述**: {step.description}")
            if step.tool_name:
                lines.append(f"- **工具**: `{step.tool_name}`")
            if step.dependencies:
                lines.append(f"- **依赖**: {', '.join(step.dependencies)}")
            if step.required_skills:
                lines.append(f"- **所需技能**: {', '.join(step.required_skills)}")
            if step.required_mcp_tools:
                lines.append(f"- **所需 MCP 工具**: {', '.join(step.required_mcp_tools)}")
            lines.append("")
        
        lines.extend([
            "---",
            "",
            "# 任务依赖关系",
        ])
        
        for i, step in enumerate(plan.steps):
            if step.dependencies:
                lines.append(f"- [任务 {i+1}] 依赖于 {step.dependencies}")
        
        return "\n".join(lines)
    
    def _generate_checklist_md(self, plan: Plan) -> str:
        """Generate checklist.md content."""
        lines = [
            f"# {plan.title} - 验收清单",
            "",
        ]
        
        categories = {}
        for item in plan.checklist.items:
            cat = item.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        
        category_names = {
            "implementation": "实现检查",
            "testing": "测试检查",
            "validation": "验证检查",
        }
        
        for cat, items in categories.items():
            cat_name = category_names.get(cat, cat)
            lines.append(f"## {cat_name}")
            for item in items:
                check_marker = "[x]" if item.checked else "[ ]"
                lines.append(f"- {check_marker} {item.description}")
            lines.append("")
        
        if not plan.checklist.items:
            lines.extend([
                "## 实现检查",
                "- [ ] 代码实现符合规范",
                "- [ ] 功能正确实现",
                "",
                "## 测试检查",
                "- [ ] 单元测试通过",
                "- [ ] 集成测试通过",
                "",
                "## 验证检查",
                "- [ ] 功能验证通过",
                "- [ ] 用户验收通过",
            ])
        
        return "\n".join(lines)
    
    async def generate_simple_plan(
        self,
        task: str,
        available_tools: list[str] | None = None,
    ) -> Plan:
        """
        Generate a simple plan without LLM (rule-based).
        
        Useful as fallback when LLM is unavailable.
        
        Args:
            task: The task description
            available_tools: List of available tool names (unused in rule-based)
        
        Returns:
            A Plan object generated using rules
        """
        result = await self._generate_with_rules(
            task=task,
            strategy_context=StrategyContext(task=task),
        )
        
        if result.success and result.plan:
            return result.plan
        
        title = f"Plan: {task[:50]}..."
        safe_title = self._sanitize_title(title)
        short_id = str(uuid.uuid4())[:8]
        plan_id = f"{safe_title}-{short_id}"
        
        return Plan(
            id=plan_id,
            title=title,
            description=task,
            steps=[PlanStep(
                id="step_1",
                description=task,
                tool_name=None,
                parameters={},
            )],
        )
    
    async def generate_with_retry(
        self,
        task: str,
        available_tools: list[str] | None = None,
        context: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> GenerationResult:
        """
        Generate a plan with automatic retry on failure.
        
        Args:
            task: The task description
            available_tools: List of available tool names
            context: Additional context for planning
            max_retries: Maximum number of retry attempts
        
        Returns:
            GenerationResult with the plan or error
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            result = await self.generate(
                task=task,
                available_tools=available_tools,
                context=context,
            )
            
            if result.success:
                return result
            
            last_error = result.error
            
            if result.metadata.get("error_code"):
                from horbot.agent.planner.errors import PlannerErrorCode
                error_code = PlannerErrorCode(result.metadata["error_code"])
                if not ErrorRecovery.should_retry(
                    type('Error', (), {'code': error_code})()
                ):
                    break
        
        return GenerationResult(
            success=False,
            error=last_error,
            metadata={"attempts": max_retries + 1},
        )
