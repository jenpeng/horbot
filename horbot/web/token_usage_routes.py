"""Token usage API routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter


router = APIRouter()


def _parse_optional_datetime(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("/token-usage/stats")
async def get_token_usage_stats(
    start_date: str = None,
    end_date: str = None,
):
    """Get token usage statistics."""
    from horbot.agent.token_tracker import get_token_tracker

    tracker = get_token_tracker()
    stats = tracker.get_stats(
        start_time=_parse_optional_datetime(start_date),
        end_time=_parse_optional_datetime(end_date),
    )

    return {
        "total_input_tokens": stats["total"]["prompt_tokens"],
        "total_output_tokens": stats["total"]["completion_tokens"],
        "total_tokens": stats["total"]["total_tokens"],
        "total_requests": stats["total"]["requests"],
        "total_cost": stats["total"]["estimated_cost"],
        "by_provider": {
            provider: {
                "input": data["prompt_tokens"],
                "output": data["completion_tokens"],
                "total": data["total_tokens"],
                "cost": round(data.get("cost", 0), 4),
            }
            for provider, data in stats["by_provider"].items()
        },
        "by_model": {
            model: {
                "input": data["prompt_tokens"],
                "output": data["completion_tokens"],
                "total": data["total_tokens"],
                "cost": round(data.get("cost", 0), 4),
            }
            for model, data in stats["by_model"].items()
        },
        "by_day": [
            {
                "date": date,
                "input": data["prompt_tokens"],
                "output": data["completion_tokens"],
                "total": data["total_tokens"],
                "cost": round(data.get("cost", 0), 4),
            }
            for date, data in stats["by_date"].items()
        ],
    }


@router.get("/token-usage/records")
async def get_token_usage_records(
    provider: str = None,
    model: str = None,
    session_id: str = None,
    start_date: str = None,
    end_date: str = None,
    limit: int = 100,
):
    """Get token usage records."""
    from horbot.agent.token_tracker import get_token_tracker

    tracker = get_token_tracker()
    records = tracker.query(
        provider=provider,
        model=model,
        session_id=session_id,
        start_time=_parse_optional_datetime(start_date),
        end_time=_parse_optional_datetime(end_date),
        limit=limit,
    )
    return {
        "records": [record.to_dict() for record in records],
        "total": len(records),
    }
