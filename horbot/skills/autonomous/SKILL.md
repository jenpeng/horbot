---
name: autonomous
description: Enable autonomous planning and execution for complex tasks with safety controls. Use when tasks require multi-step planning, task decomposition, or complex workflows that need coordination.
always: false
requires:
  config: ["autonomous.enabled"]
---

# Autonomous Execution Skill

Enable the agent to autonomously plan, execute, and monitor complex multi-step tasks.

## Capabilities

When this skill is active, the agent can:

1. **Analyze Task Complexity** - Determine if a task needs planning mode
2. **Generate Execution Plans** - Create structured plans with dependencies
3. **Execute Step by Step** - Run plans with progress tracking
4. **Handle Errors** - Retry failed steps or adapt the plan
5. **Report Progress** - Keep users informed of execution status

## Safety Rules

The following safety rules are enforced:

- Maximum 10 steps per plan (configurable)
- Each step has 5-minute timeout (configurable)
- Sensitive operations require user confirmation
- Core files are read-only (protected paths)
- All operations are logged for audit

## Configuration

Enable in your `config.json`:

```json
{
  "autonomous": {
    "enabled": true,
    "max_plan_steps": 10,
    "step_timeout": 300,
    "total_timeout": 3600,
    "retry_count": 3,
    "retry_delay": 5,
    "confirm_sensitive": true,
    "sensitive_operations": ["write_file", "edit_file", "exec"],
    "protected_paths": ["~/.ssh", "~/.env", "**/config.json"]
  },
  "tools": {
    "permission": {
      "profile": "balanced",
      "allow": ["group:fs", "group:web"],
      "deny": ["group:automation"],
      "confirm": ["group:runtime"]
    }
  }
}
```

## Permission Profiles

Choose a profile that matches your security needs:

| Profile | Description | Allowed | Denied | Confirm |
|---------|-------------|---------|--------|---------|
| `minimal` | Safest, read-only | - | runtime, automation | - |
| `balanced` | Default, good for most tasks | fs, web | automation | runtime |
| `coding` | For development work | fs, web, runtime | automation | - |
| `readonly` | Pure research | read, list_dir, web | write, edit, runtime, automation | - |
| `full` | All tools enabled | all | - | - |

## Usage

Simply describe your complex task, and the agent will:

1. **Analyze** - Assess task complexity and determine if planning is needed
2. **Plan** - Generate a structured execution plan
3. **Confirm** - Ask for your approval (if needed)
4. **Execute** - Run each step with monitoring
5. **Report** - Provide results and summary

### Example Tasks

```
"Refactor the authentication module to use OAuth2"
→ Plan: 1) Analyze current code, 2) Design OAuth2 flow, 3) Implement, 4) Test

"Set up a CI/CD pipeline for this project"
→ Plan: 1) Create config files, 2) Add build scripts, 3) Configure deployment

"Research and summarize the latest AI agent frameworks"
→ Plan: 1) Search for frameworks, 2) Analyze features, 3) Create comparison
```

## Tool Groups

Tools are organized into groups for permission management:

- **fs** - File system tools: `read_file`, `write_file`, `edit_file`, `list_dir`
- **web** - Web tools: `web_search`, `web_fetch`
- **runtime** - Command execution: `exec`
- **automation** - Background tasks: `spawn`, `cron`
- **messaging** - User communication: `message`

## Audit Logging

All tool executions are logged to `workspace/.audit/audit-YYYY-MM-DD.jsonl`

Query logs programmatically:
```python
from horbot.agent.audit import get_audit_logger

logger = get_audit_logger()
entries = logger.query(tool_name="exec", has_error=True, limit=10)
```

## Error Handling

When a step fails, the agent can:

1. **Retry** - Automatically retry with configurable delay
2. **Adapt** - Modify the plan based on the error
3. **Rollback** - Undo previous steps if needed
4. **Report** - Provide detailed error information

## Progress Commands

During execution, you can use these commands:

- `status` - Show current progress
- `pause` - Pause execution
- `resume` - Resume paused task
- `cancel` - Cancel current task
- `confirm <id>` - Approve a pending operation
- `reject <id>` - Reject a pending operation

## Best Practices

1. **Start with `balanced` profile** - Good security/usability tradeoff
2. **Enable `confirm_sensitive`** - Prevent accidental data loss
3. **Review audit logs** - Monitor what the agent is doing
4. **Use `readonly` for research** - Safe exploration without modifications
5. **Customize `protected_paths`** - Add your sensitive files

## Limitations

- Maximum plan steps: 10 (configurable)
- Step timeout: 5 minutes (configurable)
- Total timeout: 1 hour (configurable)
- No recursive planning (plans cannot spawn sub-plans)
- Confirmation timeout: 5 minutes (auto-reject)
