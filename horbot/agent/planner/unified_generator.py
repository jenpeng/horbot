"""Unified plan generator using single prompt approach.

Based on learn-claude-code theory:
- Agent IS the Model, not a framework
- Agency is learned, not programmed
- Use single prompt, not prompt chains
- Let model decide complexity, strategy, and decomposition

This generator provides a minimal harness that:
1. Provides tool descriptions to the model
2. Lets the model decide if planning is needed
3. Lets the model decide how to decompose tasks
4. Lets the model decide execution order
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid

from loguru import logger
from horbot.agent.planner.models import Plan, PlanStep, PlanStatus


UNIFIED_PLANNING_PROMPT = """You are an autonomous planning agent. Your job is to analyze tasks and create execution plans.

## Your Capabilities

You have access to the following tools:
{tools_description}

## Your Task

{task}

## Your Autonomy

You have full autonomy to decide:
1. **Is planning needed?** - Simple tasks may not need a plan
2. **How complex is this?** - You decide the complexity level
3. **How to decompose?** - You decide the steps and their granularity
4. **What tools to use?** - You choose which tools are needed
5. **Execution order?** - You determine dependencies and parallelization
6. **Validation criteria?** - You define what "done" looks like

## Output Format

If you decide planning IS needed, respond with a JSON plan:

```json
{{
  "needs_plan": true,
  "complexity": "simple|moderate|complex",
  "title": "Plan title",
  "understanding": "Your understanding of the task",
  "steps": [
    {{
      "id": "step_1",
      "description": "What this step does",
      "tools": ["tool_name"],
      "expected_result": "What you expect to achieve",
      "dependencies": []
    }}
  ],
  "validation": [
    "Criteria 1 for success",
    "Criteria 2 for success"
  ]
}}
```

If you decide planning is NOT needed, respond with:

```json
{{
  "needs_plan": false,
  "reason": "Why planning is not needed",
  "suggested_action": "What to do instead"
}}
```

## Important

- You are in control. Make your own decisions.
- Don't follow a template rigidly - adapt to the task.
- Output ONLY the JSON, no other text.
"""


@dataclass
class ToolDescription:
    """Description of a tool for the model."""
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = [f"### {self.name}", "", self.description]
        
        if self.parameters:
            lines.append("")
            lines.append("**Parameters:**")
            for param, desc in self.parameters.items():
                lines.append(f"- `{param}`: {desc}")
        
        if self.examples:
            lines.append("")
            lines.append("**Examples:**")
            for ex in self.examples:
                lines.append(f"- {ex}")
        
        return "\n".join(lines)


class UnifiedPlanGenerator:
    """
    Unified plan generator using single prompt approach.
    
    Key differences from legacy generator:
    1. Single prompt instead of three-stage chain
    2. Model decides complexity, not hardcoded rules
    3. Model decides strategy, not rule matching
    4. Model decides decomposition, not templates
    """
    
    def __init__(
        self,
        provider,
        model: str | None = None,
        max_steps: int = 20,
        tools: list[ToolDescription] | None = None,
    ):
        self.provider = provider
        self.model = model
        self.max_steps = max_steps
        self.tools = tools or []
    
    def _build_tools_description(self) -> str:
        """Build tools description for the prompt."""
        if not self.tools:
            return "No specific tools configured. Use general problem-solving capabilities."
        
        descriptions = [tool.to_markdown() for tool in self.tools]
        return "\n\n".join(descriptions)
    
    async def generate(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> Plan | None:
        """
        Generate a plan using single prompt approach.
        
        The model decides:
        - Whether planning is needed
        - How to decompose the task
        - What tools to use
        - Execution order
        
        Returns:
            Plan if model decides one is needed, None otherwise
        """
        tools_desc = self._build_tools_description()
        
        prompt = UNIFIED_PLANNING_PROMPT.format(
            tools_description=tools_desc,
            task=task,
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = await self.provider.chat(
                messages=messages,
                model=self.model,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Failed to call provider: {e}")
            return None
        
        if hasattr(response, 'content'):
            content = response.content or ""
        elif isinstance(response, dict):
            content = response.get("content", "")
        else:
            content = str(response)
        
        logger.info(f"Unified planner response length: {len(content)}")
        logger.debug(f"Unified planner response: {content[:500]}...")
        
        plan_data = self._parse_response(content)
        
        if plan_data is None:
            logger.warning(f"Failed to parse plan response: {content[:200]}...")
            return None
        
        if not plan_data.get("needs_plan", True):
            logger.info("Model decided no plan is needed")
            return None
        
        return self._build_plan(plan_data, task)
    
    def _parse_response(self, content: str) -> dict[str, Any] | None:
        """Parse model response to extract plan JSON."""
        
        if not content or not content.strip():
            logger.warning("Empty response content")
            return None
        
        content = content.strip()
        
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                logger.info("Parsed JSON from code block")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from code block: {e}")
        
        try:
            result = json.loads(content)
            logger.info("Parsed JSON directly")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse JSON directly: {e}")
        
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            json_str = content[json_start:json_end]
            try:
                result = json.loads(json_str)
                logger.info(f"Parsed JSON from substring (pos {json_start}-{json_end})")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON substring: {e}")
                logger.debug(f"JSON substring: {json_str[:200]}...")
        
        logger.warning(f"Could not extract JSON from response: {content[:200]}...")
        return None
    
    def _build_plan(self, plan_data: dict[str, Any], original_task: str) -> Plan:
        """Build Plan object from model output."""
        plan_id = str(uuid.uuid4())[:8]
        
        steps = []
        for i, step_data in enumerate(plan_data.get("steps", [])):
            step = PlanStep(
                id=step_data.get("id", f"step_{i+1}"),
                description=step_data.get("description", ""),
                tool_name=step_data.get("tools", [None])[0] if step_data.get("tools") else None,
                parameters=step_data.get("parameters", {}),
                dependencies=step_data.get("dependencies", []),
                required_skills=step_data.get("skills", []),
                required_mcp_tools=step_data.get("mcp_tools", []),
            )
            steps.append(step)
        
        return Plan(
            id=plan_id,
            title=plan_data.get("title", "Execution Plan"),
            description=plan_data.get("understanding", original_task),
            steps=steps,
            status=PlanStatus.PENDING,
            created_at=datetime.now().isoformat(),
            metadata={
                "complexity": plan_data.get("complexity", "moderate"),
                "validation": plan_data.get("validation", []),
                "generator": "unified",
            },
        )


def get_default_tools() -> list[ToolDescription]:
    """Get default tool descriptions for planning."""
    return [
        ToolDescription(
            name="read_file",
            description="Read contents of a file from the filesystem",
            parameters={
                "file_path": "Absolute path to the file to read",
            },
            examples=["Read configuration file", "View source code"],
        ),
        ToolDescription(
            name="write_file",
            description="Write content to a file, creating or overwriting it",
            parameters={
                "file_path": "Absolute path to the file to write",
                "content": "Content to write to the file",
            },
            examples=["Create new file", "Update configuration"],
        ),
        ToolDescription(
            name="edit_file",
            description="Make targeted edits to an existing file using search and replace",
            parameters={
                "file_path": "Path to the file to edit",
                "old_str": "Text to search for",
                "new_str": "Text to replace with",
            },
            examples=["Fix a bug", "Update a function"],
        ),
        ToolDescription(
            name="run_command",
            description="Execute a shell command and return the output",
            parameters={
                "command": "The command to execute",
                "cwd": "Working directory for the command",
            },
            examples=["Run tests", "Install dependencies", "Build project"],
        ),
        ToolDescription(
            name="search",
            description="Search for code patterns across the codebase",
            parameters={
                "pattern": "Search pattern or query",
                "path": "Directory to search in",
            },
            examples=["Find function definitions", "Locate usages"],
        ),
        ToolDescription(
            name="web_search",
            description="Search the web for information",
            parameters={
                "query": "Search query",
            },
            examples=["Find documentation", "Research solutions"],
        ),
    ]
