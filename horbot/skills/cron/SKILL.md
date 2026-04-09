---
name: cron
description: Schedule reminders and recurring tasks with flexible delivery options.
---

# Cron

Use the `cron` tool to schedule reminders or recurring tasks with multi-channel delivery support.

## Actions

| Action | Description |
|--------|-------------|
| `add` | Create a new scheduled task |
| `list` | List all scheduled tasks |
| `remove` | Remove a task by ID |
| `enable` | Enable a disabled task |
| `disable` | Disable an enabled task |

## Schedule Types

| Type | Parameter | Example |
|------|-----------|---------|
| **Interval** | `every_seconds` | Every hour: `every_seconds=3600` |
| **Cron** | `cron_expr` | Daily at 9am: `cron_expr="0 9 * * *"` |
| **One-time** | `at` | Specific time: `at="2026-03-20T10:30:00"` |

## Delivery Channels

The `channels` parameter allows delivering results to multiple destinations:

| Channel | Description | `to` Format |
|---------|-------------|-------------|
| `web` | Web session | Session ID |
| `whatsapp` | WhatsApp | Phone number |
| `telegram` | Telegram | Chat ID |
| `feishu` | Feishu/Lark | Chat ID |
| `sharecrm` | ShareCRM | Chat ID |
| `email` | Email | Email address |

## Examples

### Basic Reminder
```
cron(action="add", message="Drink water!", every_seconds=7200)
```

### Daily Task with Timezone
```
cron(action="add", message="Generate daily report", cron_expr="0 9 * * *", tz="Asia/Shanghai")
```

### Weekday Reminder
```
cron(action="add", message="Standup meeting reminder", cron_expr="0 10 * * 1-5", tz="Asia/Shanghai")
```

### One-time Task
```
cron(action="add", message="Meeting in 1 hour", at="2026-03-20T14:00:00")
```

### Multi-channel Delivery
```
cron(
  action="add",
  message="Important alert!",
  every_seconds=3600,
  channels=[
    {"channel": "web", "to": "session_123"},
    {"channel": "telegram", "to": "123456789"}
  ]
)
```

### Without Notification
```
cron(action="add", message="Background task", every_seconds=3600, notify=false)
```

### Task Management
```
cron(action="list")
cron(action="remove", job_id="abc123")
cron(action="disable", job_id="abc123")
cron(action="enable", job_id="abc123")
```

## Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `action` | string | Required. "add", "list", "remove", "enable", "disable" |
| `name` | string | Task name (optional, defaults to message prefix) |
| `message` | string | Task message/prompt to execute |
| `every_seconds` | integer | Interval in seconds for recurring tasks |
| `cron_expr` | string | Cron expression (e.g., "0 9 * * *") |
| `tz` | string | IANA timezone (e.g., "Asia/Shanghai") |
| `at` | string | ISO datetime for one-time execution |
| `channels` | array | Delivery channels: `[{"channel": "...", "to": "..."}]` |
| `deliver` | boolean | Whether to deliver results. Default: true |
| `notify` | boolean | Send system notification (MacOS). Default: true |
| `job_id` | string | Job ID (for remove, enable, disable) |

## Time Expressions

| User says | Parameters |
|-----------|------------|
| every 20 minutes | `every_seconds: 1200` |
| every hour | `every_seconds: 3600` |
| every day at 8am | `cron_expr: "0 8 * * *"` |
| weekdays at 5pm | `cron_expr: "0 17 * * 1-5"` |
| 9am Shanghai time daily | `cron_expr: "0 9 * * *", tz: "Asia/Shanghai"` |
| at a specific time | `at: ISO datetime string` |

## Cron Expression Format

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday = 0)
│ │ │ │ │
* * * * *
```

Examples:
- `0 9 * * *` - Every day at 9:00 AM
- `0 9 * * 1-5` - Weekdays at 9:00 AM
- `30 14 * * 1` - Every Monday at 2:30 PM
- `0 0 1 * *` - First day of every month at midnight

## Timezone

Use `tz` with `cron_expr` to schedule in a specific IANA timezone. Without `tz`, the server's local timezone is used.

Common timezones:
- `Asia/Shanghai` - China Standard Time
- `America/New_York` - US Eastern Time
- `America/Vancouver` - US Pacific Time
- `Europe/London` - UK Time
- `UTC` - Coordinated Universal Time

## Notifications

By default, cron jobs send a MacOS system notification when triggered. Set `notify=false` to disable this.
