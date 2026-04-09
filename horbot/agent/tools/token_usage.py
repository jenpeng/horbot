"""Token usage statistics tool for AI agents."""

from datetime import datetime, timedelta
from typing import Any

from horbot.agent.tools.base import Tool, ToolCategory, register_tool
from horbot.agent.token_tracker import get_token_tracker


@register_tool(category=ToolCategory.RUNTIME, tags=["stats", "tokens", "usage", "cost"])
class TokenUsageTool(Tool):
    """Query token usage statistics and cost estimates."""
    
    @property
    def name(self) -> str:
        return "token_usage"
    
    @property
    def description(self) -> str:
        return """Query token usage statistics for the AI assistant.

Returns detailed statistics including:
- Total tokens used (prompt + completion)
- Estimated costs
- Usage breakdown by provider, model, and date
- Request counts

Use this to track API costs and usage patterns."""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Time period for statistics. Options: 'today', 'week', 'month', 'all'. Default: 'month'",
                    "enum": ["today", "week", "month", "all"],
                },
                "group_by": {
                    "type": "string",
                    "description": "How to group the results. Options: 'model', 'provider', 'date'. Default: shows all groupings",
                    "enum": ["model", "provider", "date"],
                },
                "detailed": {
                    "type": "boolean",
                    "description": "Whether to include detailed breakdown. Default: false (summary only)",
                },
            },
        }
    
    async def execute(
        self,
        period: str = "month",
        group_by: str | None = None,
        detailed: bool = False,
    ) -> str:
        tracker = get_token_tracker()
        
        now = datetime.now()
        if period == "today":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_time = now - timedelta(days=7)
        elif period == "month":
            start_time = now - timedelta(days=30)
        else:
            start_time = None
        
        stats = tracker.get_stats(start_time=start_time, end_time=now)
        
        return self._format_stats(stats, group_by, detailed, period)
    
    def _format_stats(
        self,
        stats: dict[str, Any],
        group_by: str | None,
        detailed: bool,
        period: str,
    ) -> str:
        total = stats["total"]
        
        lines = [
            f"📊 Token Usage Statistics ({period})",
            "=" * 40,
            "",
            "📈 Summary:",
            f"  • Total Requests: {total['requests']:,}",
            f"  • Prompt Tokens: {total['prompt_tokens']:,}",
            f"  • Completion Tokens: {total['completion_tokens']:,}",
            f"  • Total Tokens: {total['total_tokens']:,}",
            f"  • Estimated Cost: ${total['estimated_cost']:.4f}",
            "",
        ]
        
        if total['requests'] == 0:
            lines.append("No token usage data found for this period.")
            return "\n".join(lines)
        
        if group_by == "model" or group_by is None:
            by_model = stats.get("by_model", {})
            if by_model:
                lines.append("🤖 By Model:")
                for model, data in sorted(by_model.items(), key=lambda x: x[1]["total_tokens"], reverse=True):
                    lines.append(f"  {model}:")
                    lines.append(f"    Requests: {data['requests']:,}")
                    lines.append(f"    Tokens: {data['total_tokens']:,} (prompt: {data['prompt_tokens']:,}, completion: {data['completion_tokens']:,})")
                    lines.append(f"    Cost: ${data['cost']:.4f}")
                lines.append("")
        
        if group_by == "provider" or group_by is None:
            by_provider = stats.get("by_provider", {})
            if by_provider:
                lines.append("🏢 By Provider:")
                for provider, data in sorted(by_provider.items(), key=lambda x: x[1]["total_tokens"], reverse=True):
                    lines.append(f"  {provider}:")
                    lines.append(f"    Requests: {data['requests']:,}")
                    lines.append(f"    Tokens: {data['total_tokens']:,}")
                    lines.append(f"    Cost: ${data['cost']:.4f}")
                lines.append("")
        
        if (group_by == "date" or group_by is None) and detailed:
            by_date = stats.get("by_date", {})
            if by_date:
                lines.append("📅 By Date (last 7 days):")
                sorted_dates = sorted(by_date.items(), reverse=True)[:7]
                for date, data in sorted_dates:
                    lines.append(f"  {date}:")
                    lines.append(f"    Requests: {data['requests']:,}")
                    lines.append(f"    Tokens: {data['total_tokens']:,}")
                    lines.append(f"    Cost: ${data['cost']:.4f}")
                lines.append("")
        
        return "\n".join(lines)
