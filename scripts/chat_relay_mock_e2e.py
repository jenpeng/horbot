#!/usr/bin/env python3
"""Run a local mock SSE regression for A -> B -> A relay flows."""

from __future__ import annotations

import asyncio
import json
import sys

from horbot.testing.mock_chat_relay import run_mock_relay_stream_test


def main() -> int:
    result = asyncio.run(run_mock_relay_stream_test())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
