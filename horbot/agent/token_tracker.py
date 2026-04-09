"""Token usage tracking module."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import threading
from collections import defaultdict


@dataclass
class TokenUsageRecord:
    """Single token usage record."""
    timestamp: str
    session_id: str | None = None
    provider: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class TokenTracker:
    """
    Thread-safe token usage tracker.
    
    Features:
    - JSON Lines format for easy parsing
    - Thread-safe writes
    - Automatic log rotation
    - Statistics aggregation
    """
    
    def __init__(
        self,
        log_dir: Path | str | None = None,
        max_file_size_mb: int = 10,
        max_files: int = 30,
    ):
        if log_dir:
            self._log_dir = Path(log_dir)
        else:
            from horbot.utils.paths import get_token_usage_dir

            self._log_dir = get_token_usage_dir()
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._max_file_size = max_file_size_mb * 1024 * 1024
        self._max_files = max_files
        self._lock = threading.Lock()
        
        self._pricing: dict[str, dict[str, float]] = {
            "gpt-4o": {"prompt": 2.5 / 1_000_000, "completion": 10.0 / 1_000_000},
            "gpt-4o-mini": {"prompt": 0.15 / 1_000_000, "completion": 0.6 / 1_000_000},
            "gpt-4-turbo": {"prompt": 10.0 / 1_000_000, "completion": 30.0 / 1_000_000},
            "gpt-4": {"prompt": 30.0 / 1_000_000, "completion": 60.0 / 1_000_000},
            "gpt-3.5-turbo": {"prompt": 0.5 / 1_000_000, "completion": 1.5 / 1_000_000},
            "claude-3-5-sonnet": {"prompt": 3.0 / 1_000_000, "completion": 15.0 / 1_000_000},
            "claude-3-opus": {"prompt": 15.0 / 1_000_000, "completion": 75.0 / 1_000_000},
            "claude-3-sonnet": {"prompt": 3.0 / 1_000_000, "completion": 15.0 / 1_000_000},
            "claude-3-haiku": {"prompt": 0.25 / 1_000_000, "completion": 1.25 / 1_000_000},
            "gemini-1.5-pro": {"prompt": 1.25 / 1_000_000, "completion": 5.0 / 1_000_000},
            "gemini-1.5-flash": {"prompt": 0.075 / 1_000_000, "completion": 0.3 / 1_000_000},
            # Deepseek models
            "deepseek": {"prompt": 2.0 / 1_000_000, "completion": 3.0 / 1_000_000},
            "deepseek-reasoner": {"prompt": 2.0 / 1_000_000, "completion": 8.0 / 1_000_000},
            # MiniMax models
            "minimax": {"prompt": 1.0 / 1_000_000, "completion": 1.5 / 1_000_000},
            "minimax-m2.5": {"prompt": 0.4 / 1_000_000, "completion": 4.0 / 1_000_000},
            # SiliconFlow (for various open models)
            "siliconflow": {"prompt": 1.0 / 1_000_000, "completion": 1.5 / 1_000_000},
            # Default fallback
            "default": {"prompt": 1.0 / 1_000_000, "completion": 3.0 / 1_000_000},
        }
    
    def _get_log_file(self) -> Path:
        today = datetime.now().strftime("%Y-%m")
        return self._log_dir / f"token-usage-{today}.jsonl"
    
    def _rotate_if_needed(self, file_path: Path) -> None:
        if not file_path.exists():
            return
        
        if file_path.stat().st_size >= self._max_file_size:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            rotated = file_path.with_suffix(f".{timestamp}.jsonl")
            file_path.rename(rotated)
            self._cleanup_old_files()
    
    def _cleanup_old_files(self) -> None:
        log_files = sorted(
            self._log_dir.glob("token-usage-*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        
        for old_file in log_files[self._max_files:]:
            try:
                old_file.unlink()
            except Exception:
                pass
    
    def record(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        session_id: str | None = None,
    ) -> None:
        """Record a token usage event."""
        record = TokenUsageRecord(
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        
        with self._lock:
            log_file = self._get_log_file()
            self._rotate_if_needed(log_file)
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(record.to_json() + "\n")
    
    def _get_model_key(self, model: str) -> str:
        model_lower = model.lower()
        for key in self._pricing:
            if key in model_lower:
                return key
        return "default"
    
    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost for token usage."""
        model_key = self._get_model_key(model)
        pricing = self._pricing.get(model_key, self._pricing["default"])
        return (
            prompt_tokens * pricing["prompt"] +
            completion_tokens * pricing["completion"]
        )
    
    def query(
        self,
        session_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[TokenUsageRecord]:
        """Query token usage records with filters."""
        results: list[TokenUsageRecord] = []
        
        log_files = sorted(
            self._log_dir.glob("token-usage-*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        
        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            record = TokenUsageRecord(**data)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        
                        if session_id and record.session_id != session_id:
                            continue
                        if provider and record.provider != provider:
                            continue
                        if model and record.model != model:
                            continue
                        if start_time:
                            record_time = datetime.fromisoformat(record.timestamp)
                            if record_time.tzinfo is None and start_time.tzinfo is not None:
                                from datetime import timezone
                                record_time = record_time.replace(tzinfo=timezone.utc)
                            if record_time < start_time:
                                continue
                        if end_time:
                            record_time = datetime.fromisoformat(record.timestamp)
                            if record_time.tzinfo is None and end_time.tzinfo is not None:
                                from datetime import timezone
                                record_time = record_time.replace(tzinfo=timezone.utc)
                            if record_time > end_time:
                                continue
                        
                        results.append(record)
                        if len(results) >= limit:
                            return results
            except Exception:
                continue
        
        return results
    
    def get_stats(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get aggregated statistics."""
        if start_time is None:
            start_time = datetime.now() - timedelta(days=30)
        if end_time is None:
            end_time = datetime.now()
        
        records = self.query(start_time=start_time, end_time=end_time, limit=100000)
        
        total_prompt = 0
        total_completion = 0
        total_tokens = 0
        total_cost = 0.0
        
        by_provider: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0,
            "cost": 0.0,
        })
        
        by_model: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0,
            "cost": 0.0,
        })
        
        by_date: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0,
            "cost": 0.0,
        })
        
        for record in records:
            total_prompt += record.prompt_tokens
            total_completion += record.completion_tokens
            total_tokens += record.total_tokens
            
            cost = self.estimate_cost(
                record.model,
                record.prompt_tokens,
                record.completion_tokens
            )
            total_cost += cost
            
            by_provider[record.provider]["prompt_tokens"] += record.prompt_tokens
            by_provider[record.provider]["completion_tokens"] += record.completion_tokens
            by_provider[record.provider]["total_tokens"] += record.total_tokens
            by_provider[record.provider]["requests"] += 1
            by_provider[record.provider]["cost"] += cost
            
            by_model[record.model]["prompt_tokens"] += record.prompt_tokens
            by_model[record.model]["completion_tokens"] += record.completion_tokens
            by_model[record.model]["total_tokens"] += record.total_tokens
            by_model[record.model]["requests"] += 1
            by_model[record.model]["cost"] += cost
            
            date_key = record.timestamp[:10]
            by_date[date_key]["prompt_tokens"] += record.prompt_tokens
            by_date[date_key]["completion_tokens"] += record.completion_tokens
            by_date[date_key]["total_tokens"] += record.total_tokens
            by_date[date_key]["requests"] += 1
            by_date[date_key]["cost"] += cost
        
        return {
            "period": {
                "start": start_time.isoformat() if start_time else None,
                "end": end_time.isoformat() if end_time else None,
            },
            "total": {
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "total_tokens": total_tokens,
                "requests": len(records),
                "estimated_cost": round(total_cost, 4),
            },
            "by_provider": dict(by_provider),
            "by_model": dict(by_model),
            "by_date": dict(sorted(by_date.items())),
        }


_global_tracker: TokenTracker | None = None


def get_token_tracker() -> TokenTracker:
    """Get the global token tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        from horbot.config.loader import get_cached_config
        config = get_cached_config()
        log_dir = config.workspace_path / "token_usage"
        _global_tracker = TokenTracker(log_dir=log_dir)
    return _global_tracker


def set_token_tracker(tracker: TokenTracker) -> None:
    """Set the global token tracker instance."""
    global _global_tracker
    _global_tracker = tracker
