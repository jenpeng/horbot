"""Subagent for executing plan steps with detailed logging and monitoring."""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Dict, List

from loguru import logger

from horbot.providers.base import LLMProvider
from horbot.agent.tools.registry import ToolRegistry


class StepExecutionStatus(Enum):
    """Status of step execution."""
    PENDING = "pending"
    RUNNING = "running"
    THINKING = "thinking"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionLogEntry:
    """A single entry in the execution log."""
    timestamp: float
    type: str  # "thinking", "tool_call", "tool_result", "completion"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "type": self.type,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass
class StepExecutionResult:
    """Result of executing a plan step."""
    step_id: str
    status: StepExecutionStatus
    result: str
    execution_time: float
    logs: List[ExecutionLogEntry]
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "status": self.status.value,
            "result": self.result,
            "execution_time": self.execution_time,
            "logs": [log.to_dict() for log in self.logs],
            "tool_calls": self.tool_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


class PlanStepSubagent:
    """A subagent dedicated to executing a single plan step with detailed logging."""
    
    def __init__(
        self,
        step_id: str,
        step_description: str,
        plan_context: str,
        provider: LLMProvider,
        tools: ToolRegistry,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        max_iterations: int = 15,
        session_key: Optional[str] = None,
        required_skills: Optional[List[str]] = None,
        required_mcp_tools: Optional[List[str]] = None,
    ):
        self.step_id = step_id
        self.step_description = step_description
        self.plan_context = plan_context
        self.provider = provider
        self.tools = tools
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.session_key = session_key
        self.required_skills = required_skills or []
        self.required_mcp_tools = required_mcp_tools or []
        
        self.status = StepExecutionStatus.PENDING
        self.logs: List[ExecutionLogEntry] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self._current_iteration = 0
        self._stop_requested = False
        
    def request_stop(self):
        """Request to stop the step execution."""
        self._stop_requested = True
        logger.info("[Step {}] Stop requested", self.step_id)
        
    def _add_log(self, log_type: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add an entry to the execution log."""
        entry = ExecutionLogEntry(
            timestamp=time.time(),
            type=log_type,
            content=content,
            metadata=metadata or {},
        )
        self.logs.append(entry)
        logger.debug("[Step {}] {}: {}", self.step_id, log_type, content[:100])
        
    async def execute(self) -> StepExecutionResult:
        """Execute the plan step with detailed logging."""
        self.start_time = time.time()
        self.status = StepExecutionStatus.RUNNING
        
        # Token tracking
        total_input_tokens = 0
        total_output_tokens = 0
        
        try:
            # Build system prompt with plan context
            system_prompt = self._build_system_prompt()
            
            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请执行步骤: {self.step_description}"},
            ]
            
            self._add_log("thinking", f"开始执行步骤: {self.step_description}")
            
            final_result: Optional[str] = None
            
            while self._current_iteration < self.max_iterations:
                # Check if stop was requested
                if self._stop_requested:
                    logger.info("[Step {}] Execution stopped by user request", self.step_id)
                    self.status = StepExecutionStatus.STOPPED
                    self._add_log("error", "执行被用户停止")
                    break
                
                self._current_iteration += 1
                self.status = StepExecutionStatus.THINKING
                
                self._add_log("thinking", f"第 {self._current_iteration}/{self.max_iterations} 轮思考...")
                
                response = await self.provider.chat(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                
                # Track token usage
                if hasattr(response, 'usage'):
                    total_input_tokens += response.usage.get('prompt_tokens', 0)
                    total_output_tokens += response.usage.get('completion_tokens', 0)
                    
                    # Record to token tracker
                    from horbot.agent.token_tracker import get_token_tracker
                    try:
                        tracker = get_token_tracker()
                        provider_name = self.provider.name if hasattr(self.provider, 'name') else 'unknown'
                        model_name = self.model or 'unknown'
                        prompt_tokens = response.usage.get('prompt_tokens', 0)
                        completion_tokens = response.usage.get('completion_tokens', 0)
                        total_tokens = response.usage.get('total_tokens', 0)
                        
                        tracker.record(
                            provider=provider_name,
                            model=model_name,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens,
                            session_id=self.session_key,
                        )
                        
                        logger.info("[Step {}] Recorded token usage to tracker: provider={}, model={}, prompt={}, completion={}, session_key={}", 
                                   self.step_id, provider_name, model_name, prompt_tokens, completion_tokens, self.session_key)
                    except Exception as e:
                        logger.warning("[Step {}] Failed to record token usage: {}", self.step_id, e)
                
                # Record reasoning content if available
                if hasattr(response, 'reasoning_content') and response.reasoning_content:
                    self._add_log(
                        "thinking",
                        f"推理过程: {response.reasoning_content[:500]}...",
                        {"reasoning_content": response.reasoning_content}
                    )
                
                if response.has_tool_calls:
                    self.status = StepExecutionStatus.EXECUTING
                    
                    # Add assistant message with tool calls and reasoning_content
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in response.tool_calls
                    ]
                    assistant_message = {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": tool_call_dicts,
                    }
                    # Add reasoning_content if available (for DeepSeek reasoning models)
                    if hasattr(response, 'reasoning_content') and response.reasoning_content:
                        assistant_message["reasoning_content"] = response.reasoning_content
                    messages.append(assistant_message)
                    
                    # Execute tools and log
                    for tool_call in response.tool_calls:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        self._add_log(
                            "tool_call",
                            f"调用工具: {tool_call.name}",
                            {"tool_name": tool_call.name, "arguments": tool_call.arguments},
                        )
                        
                        try:
                            result = await self.tools.execute(tool_call.name, tool_call.arguments)
                            self._add_log(
                                "tool_result",
                                f"工具 {tool_call.name} 执行结果: {result[:200]}...",
                                {"tool_name": tool_call.name, "result": result},
                            )
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.name,
                                "content": result,
                            })
                        except Exception as e:
                            error_msg = f"工具执行失败: {str(e)}"
                            self._add_log("tool_result", error_msg, {"tool_name": tool_call.name, "error": str(e)})
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.name,
                                "content": error_msg,
                            })
                else:
                    # Record reasoning content if available
                    if hasattr(response, 'reasoning_content') and response.reasoning_content:
                        self._add_log(
                            "thinking",
                            f"推理过程: {response.reasoning_content[:500]}...",
                            {"reasoning_content": response.reasoning_content}
                        )
                    
                    final_result = response.content
                    self._add_log("completion", f"步骤执行完成: {final_result[:200]}...")
                    break
            
            if final_result is None:
                final_result = "步骤执行完成，但未生成最终响应。"
                self._add_log("completion", final_result)
            
            self.status = StepExecutionStatus.COMPLETED
            self.end_time = time.time()
            
            logger.info("[Step {}] Execution completed. Tokens: input={}, output={}", 
                       self.step_id, total_input_tokens, total_output_tokens)
            
            return StepExecutionResult(
                step_id=self.step_id,
                status=self.status,
                result=final_result,
                execution_time=self.end_time - self.start_time,
                logs=self.logs,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )
            
        except Exception as e:
            error_msg = f"步骤执行失败: {str(e)}"
            logger.error("[Step {}] {}", self.step_id, error_msg)
            self._add_log("completion", error_msg, {"error": str(e)})
            self.status = StepExecutionStatus.FAILED
            self.end_time = time.time()
            
            return StepExecutionResult(
                step_id=self.step_id,
                status=self.status,
                result=error_msg,
                execution_time=self.end_time - self.start_time,
                logs=self.logs,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )
    
    def _build_system_prompt(self) -> str:
        """Build system prompt with plan context."""
        # Get available tools for file creation
        available_tools = self.tools.get_definitions()
        file_tools = []
        for tool in available_tools:
            tool_name = tool.get("name", "")
            if any(keyword in tool_name.lower() for keyword in ["write", "create", "document", "file", "word", "docx", "ppt", "excel"]):
                file_tools.append(f"- {tool_name}: {tool.get('description', 'No description')[:100]}")
        
        file_tools_info = "\n".join(file_tools) if file_tools else "No specific file creation tools available"
        
        # Get current working directory
        import os
        current_dir = os.getcwd()
        
        # Build skills and MCP tools info
        skills_info = ""
        if self.required_skills:
            skills_info = f"""
本步骤所需的 Skills:
{chr(10).join(f'- {skill}' for skill in self.required_skills)}

请参考这些 Skills 中的指导来执行任务。
"""
        
        mcp_tools_info = ""
        if self.required_mcp_tools:
            mcp_tools_info = f"""
本步骤所需的 MCP 工具:
{chr(10).join(f'- {tool}' for tool in self.required_mcp_tools)}

请优先使用这些 MCP 工具来完成任务。
"""
        
        return f"""你是一个专业的任务执行助手。请按照以下规划上下文执行当前步骤。

{self.plan_context}

当前步骤信息:
- 步骤ID: {self.step_id}
- 步骤描述: {self.step_description}
- 当前工作目录: {current_dir}
{skills_info}{mcp_tools_info}
可用的文件创建工具:
{file_tools_info}

执行要求:
1. **任务分解原则** (重要):
   - 如果当前步骤比较复杂，应该先分解成更小的子任务
   - 每个子任务应该有明确的目标和完成标准
   - 避免在一个步骤中执行过多的工具调用
   - 如果发现自己在重复执行相同的操作，应该停下来重新思考策略

2. **高效执行策略**:
   - 先规划后执行：在执行前先思考需要哪些步骤
   - 批量处理：如果需要处理多个相似的任务，尽量一次性完成
   - 避免重复：不要重复获取相同的信息或执行相同的操作
   - 及时总结：完成关键步骤后及时总结，避免遗忘

3. **工具使用优化**:
   - 优先使用最直接的工具完成任务
   - 避免不必要的工具调用
   - 如果一个工具调用失败，不要重复尝试相同的操作，而是思考替代方案

4. **重要**: 如果步骤涉及创建文件、文档、代码等产出物，必须使用相应的工具来创建，不要只是描述内容
5. **文件路径要求**:
   - 必须使用绝对路径，不要使用相对路径
   - **关键**: 如果用户在任务描述中指定了保存路径，必须严格按照用户指定的路径保存文件，不能自行更改路径
   - 如果指定的路径目录不存在，必须先创建目录
   - 不要在用户指定的路径之外创建新的目录
6. **路径示例**:
   - 如果用户要求保存到"/Users/jenpeng/Desktop/个人/AI Project/horbot/.horbot/agents/main/workspace/Project/"
   - 那么文件必须保存到这个路径下，例如："/Users/jenpeng/Desktop/个人/AI Project/horbot/.horbot/agents/main/workspace/Project/文档名称.docx"
   - 不能保存到其他位置，如当前工作目录或其他目录
7. **工具使用示例**：
   - 创建Word文档：使用 mcp_office-word_create_document 工具，savePath 参数使用绝对路径
   - 创建PowerPoint演示文稿：使用 mcp_office-powerpoint_create_presentation 工具，savePath 参数使用绝对路径
   - 创建文本文件：使用 write_file 工具，path 参数使用绝对路径
8. 执行结果必须详细、具体、有价值
9. 如果是分析任务，必须包含详细的分析过程和结论
10. 避免简单的"完成"、"成功"等无意义的回复
11. 提供清晰的执行步骤和结果说明

**迭代限制提醒**: 你最多可以进行 {self.max_iterations} 次工具调用。如果任务非常复杂，请优先完成最核心的部分，并在回复中说明哪些部分需要后续处理。

请执行当前步骤，如果需要创建文件，请务必使用工具来创建实际的文件，并严格按照用户指定的路径保存。"""
    
    def get_execution_logs(self) -> List[ExecutionLogEntry]:
        """Get all execution logs."""
        return self.logs
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current execution status."""
        return {
            "step_id": self.step_id,
            "status": self.status.value,
            "iteration": self._current_iteration,
            "max_iterations": self.max_iterations,
            "execution_time": (time.time() - self.start_time) if self.start_time else 0,
            "log_count": len(self.logs),
        }
