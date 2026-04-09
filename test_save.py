from horbot.session.manager import SessionManager
from pathlib import Path
import asyncio
import json

team_sessions_path = Path("/Users/jenpeng/Desktop/个人/AI Project/horbot/.horbot/teams/team-001/workspace/sessions")
manager = SessionManager(workspace=team_sessions_path)
session = manager.get_or_create("test_fix_save")

session.add_message("user", "Test user message")
session.add_message("assistant", "Test assistant message", metadata={"agent_id": "test", "agent_name": "Test"})
print(f"Messages before save: {len(session.messages)}")

asyncio.run(manager.async_save(session))
print("Saved!")

with open(team_sessions_path / "test_fix_save.jsonl") as f:
    lines = f.readlines()
    print(f"Lines in file: {len(lines)}")
    for line in lines:
        data = json.loads(line)
        if data.get("_type") != "metadata":
            print(f"Message role: {data.get('role')}, has metadata: {'metadata' in data}, metadata: {data.get('metadata')}")