"""Workflow parser for YAML/JSON workflow definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from horbot.agent.workflow.models import Workflow, WorkflowStep, WorkflowVariable, StepType


class WorkflowParseError(Exception):
    """Error parsing workflow definition."""
    pass


class WorkflowParser:
    """
    Parser for workflow definitions in YAML or JSON format.
    
    Supports:
    - YAML and JSON formats
    - Variable definitions with defaults
    - Conditional steps
    - Loop constructs
    - Parallel execution
    """
    
    def __init__(self):
        self._loaded_workflows: dict[str, Workflow] = {}
    
    def parse_file(self, file_path: Path | str) -> Workflow:
        """Parse a workflow from a file."""
        path = Path(file_path)
        
        if not path.exists():
            raise WorkflowParseError(f"Workflow file not found: {file_path}")
        
        content = path.read_text(encoding="utf-8")
        
        if path.suffix in (".yaml", ".yml"):
            return self.parse_yaml(content)
        elif path.suffix == ".json":
            return self.parse_json(content)
        else:
            raise WorkflowParseError(f"Unsupported file format: {path.suffix}")
    
    def parse_yaml(self, content: str) -> Workflow:
        """Parse a workflow from YAML content."""
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise WorkflowParseError(f"YAML parsing error: {e}")
        
        return self.parse_dict(data)
    
    def parse_json(self, content: str) -> Workflow:
        """Parse a workflow from JSON content."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise WorkflowParseError(f"JSON parsing error: {e}")
        
        return self.parse_dict(data)
    
    def parse_dict(self, data: dict[str, Any]) -> Workflow:
        """Parse a workflow from a dictionary."""
        if not isinstance(data, dict):
            raise WorkflowParseError("Workflow must be a dictionary")
        
        workflow_id = data.get("id", "")
        if not workflow_id:
            raise WorkflowParseError("Workflow must have an 'id' field")
        
        name = data.get("name", workflow_id)
        
        variables = [
            self._parse_variable(v) for v in data.get("variables", [])
        ]
        
        steps = [
            self._parse_step(s) for s in data.get("steps", [])
        ]
        
        return Workflow(
            id=workflow_id,
            name=name,
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            variables=variables,
            steps=steps,
            metadata=data.get("metadata", {}),
        )
    
    def _parse_variable(self, data: dict[str, Any]) -> WorkflowVariable:
        """Parse a variable definition."""
        if not isinstance(data, dict):
            raise WorkflowParseError("Variable must be a dictionary")
        
        name = data.get("name", "")
        if not name:
            raise WorkflowParseError("Variable must have a 'name' field")
        
        return WorkflowVariable(
            name=name,
            default=data.get("default"),
            description=data.get("description", ""),
            required=data.get("required", False),
            type=data.get("type", "string"),
        )
    
    def _parse_step(self, data: dict[str, Any]) -> WorkflowStep:
        """Parse a step definition."""
        if not isinstance(data, dict):
            raise WorkflowParseError("Step must be a dictionary")
        
        step_id = data.get("id", "")
        name = data.get("name", step_id)
        
        step_type = StepType(data.get("type", "action"))
        
        sub_steps = [
            self._parse_step(s) for s in data.get("steps", [])
        ]
        
        return WorkflowStep(
            id=step_id,
            name=name,
            type=step_type,
            tool=data.get("tool"),
            parameters=data.get("parameters", {}),
            condition=data.get("condition"),
            loop_var=data.get("loop_var"),
            loop_over=data.get("loop_over"),
            steps=sub_steps,
            on_success=data.get("on_success"),
            on_failure=data.get("on_failure"),
            retry_count=data.get("retry_count", 0),
            timeout=data.get("timeout", 300),
        )
    
    def load_from_directory(self, dir_path: Path | str) -> dict[str, Workflow]:
        """Load all workflows from a directory."""
        workflows = {}
        path = Path(dir_path)
        
        if not path.exists():
            return workflows
        
        for file_path in path.glob("*.yaml"):
            try:
                workflow = self.parse_file(file_path)
                workflows[workflow.id] = workflow
            except WorkflowParseError:
                continue
        
        for file_path in path.glob("*.json"):
            try:
                workflow = self.parse_file(file_path)
                workflows[workflow.id] = workflow
            except WorkflowParseError:
                continue
        
        self._loaded_workflows.update(workflows)
        return workflows
    
    def get_workflow(self, workflow_id: str) -> Workflow | None:
        """Get a loaded workflow by ID."""
        return self._loaded_workflows.get(workflow_id)
    
    def list_workflows(self) -> list[str]:
        """List all loaded workflow IDs."""
        return list(self._loaded_workflows.keys())


EXAMPLE_WORKFLOW_YAML = """
id: code-review
name: Code Review Workflow
description: Automated code review process
version: 1.0

variables:
  - name: target_path
    description: Path to the code to review
    required: true
    type: string
  - name: output_format
    description: Output format for the report
    default: markdown
    type: string

steps:
  - id: list_files
    name: List files to review
    type: action
    tool: list_dir
    parameters:
      path: "${target_path}"
  
  - id: check_loop
    name: Review each file
    type: loop
    loop_var: file
    loop_over: "${list_files.result.files}"
    steps:
      - id: read_file
        name: Read file content
        type: action
        tool: read_file
        parameters:
          path: "${file.path}"
      
      - id: analyze
        name: Analyze code
        type: action
        condition: "${read_file.result.size} < 100000"
        tool: analyze_code
        parameters:
          content: "${read_file.result.content}"
  
  - id: generate_report
    name: Generate review report
    type: action
    tool: write_file
    parameters:
      path: "${target_path}/review-report.md"
      content: "${check_loop.result}"
"""

EXAMPLE_WORKFLOW_JSON = """
{
  "id": "research",
  "name": "Research Workflow",
  "description": "Systematic research and information gathering",
  "version": "1.0",
  "variables": [
    {
      "name": "topic",
      "description": "Research topic",
      "required": true,
      "type": "string"
    },
    {
      "name": "depth",
      "description": "Research depth",
      "default": "medium",
      "type": "string"
    }
  ],
  "steps": [
    {
      "id": "search",
      "name": "Search for information",
      "type": "action",
      "tool": "web_search",
      "parameters": {
        "query": "${topic}"
      }
    },
    {
      "id": "fetch_results",
      "name": "Fetch detailed content",
      "type": "parallel",
      "steps": [
        {
          "id": "fetch_1",
          "type": "action",
          "tool": "web_fetch",
          "parameters": {
            "url": "${search.result[0].url}"
          }
        },
        {
          "id": "fetch_2",
          "type": "action",
          "tool": "web_fetch",
          "parameters": {
            "url": "${search.result[1].url}"
          }
        }
      ]
    }
  ]
}
"""
