import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from horbot.agent.manager import get_agent_manager
from horbot.config.normalizer import normalize_config
from horbot.config.schema import AgentConfig, Config
from horbot.web.main import app


class TaskWorkspaceApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_list_update_and_list_files(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            horbot_root = root / ".horbot"
            workspace_root = root / "agents"
            config = Config()
            config.agents.defaults.workspace = str(workspace_root / "main")
            config.agents.instances = {
                "main": AgentConfig(id="main", name="Main", is_main=True, workspace=str(workspace_root / "main")),
            }
            config = normalize_config(config)

            manager = get_agent_manager()
            with (
                patch.dict("os.environ", {"HORBOT_ROOT": str(horbot_root)}),
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
            ):
                manager.reload(config)
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    create_response = await client.post(
                        "/api/task-workspaces",
                        json={
                            "title": "  Make PPT outline  ",
                            "agent_id": "main",
                            "conversation_id": "dm_main",
                            "session_key": "web:dm_main",
                        },
                    )
                    self.assertEqual(create_response.status_code, 200)
                    task = create_response.json()
                    self.assertEqual(task["title"], "Make PPT outline")
                    self.assertEqual(task["agent_id"], "main")
                    self.assertEqual(task["conversation_id"], "dm_main")
                    self.assertEqual(task["workspace_mode"], "conversation")
                    self.assertTrue(task["cwd"].endswith(f".horbot/task-workspaces/main/dm_main/{task['id']}"))
                    self.assertTrue(Path(task["cwd"]).exists())

                    second_create_response = await client.post(
                        "/api/task-workspaces",
                        json={
                            "title": "Second task",
                            "agent_id": "main",
                            "conversation_id": "dm_main",
                        },
                    )
                    self.assertEqual(second_create_response.status_code, 200)
                    second_task = second_create_response.json()
                    self.assertNotEqual(second_task["id"], task["id"])
                    self.assertNotEqual(second_task["cwd"], task["cwd"])
                    self.assertTrue(
                        second_task["cwd"].endswith(
                            f".horbot/task-workspaces/main/dm_main/{second_task['id']}"
                        )
                    )

                    (Path(task["cwd"]) / "outline.md").write_text("# Outline\n", encoding="utf-8")

                    list_response = await client.get("/api/task-workspaces?conversation_id=dm_main")
                    self.assertEqual(list_response.status_code, 200)
                    tasks = list_response.json()["task_workspaces"]
                    self.assertEqual(len(tasks), 2)
                    self.assertTrue(any(item["id"] == task["id"] for item in tasks))

                    update_response = await client.patch(
                        f"/api/task-workspaces/{task['id']}",
                        json={"status": "running", "metadata": {"source": "test"}},
                    )
                    self.assertEqual(update_response.status_code, 200)
                    updated = update_response.json()
                    self.assertEqual(updated["status"], "running")
                    self.assertEqual(updated["metadata"], {"source": "test"})

                    files_response = await client.get(f"/api/task-workspaces/{task['id']}/files")
                    self.assertEqual(files_response.status_code, 200)
                    files_payload = files_response.json()
                    self.assertTrue(files_payload["exists"])
                    self.assertTrue(any(item["path"] == "outline.md" for item in files_payload["files"]))

                    file_response = await client.get(
                        f"/api/task-workspaces/{task['id']}/file",
                        params={"path": "outline.md"},
                    )
                    self.assertEqual(file_response.status_code, 200)
                    file_payload = file_response.json()
                    self.assertEqual(file_payload["path"], "outline.md")
                    self.assertEqual(file_payload["content"], "# Outline\n")

                    blocked_file_response = await client.get(
                        f"/api/task-workspaces/{task['id']}/file",
                        params={"path": "../outside.md"},
                    )
                    self.assertEqual(blocked_file_response.status_code, 400)

                    changes_response = await client.get(f"/api/task-workspaces/{task['id']}/changes")
                    self.assertEqual(changes_response.status_code, 200)
                    changes_payload = changes_response.json()
                    self.assertEqual(changes_payload["task_id"], task["id"])
                    self.assertFalse(changes_payload["available"])
                    self.assertEqual(changes_payload["reason"], "not_git_repo")

                    missing_response = await client.get("/api/task-workspaces/not-found")
                    self.assertEqual(missing_response.status_code, 404)

                    external_cwd = root / "outside-task-workspace"
                    external_create_response = await client.post(
                        "/api/task-workspaces",
                        json={
                            "title": "External cwd",
                            "agent_id": "main",
                            "conversation_id": "dm_main",
                            "cwd": str(external_cwd),
                        },
                    )
                    self.assertEqual(external_create_response.status_code, 200)
                    external_task = external_create_response.json()
                    self.assertEqual(Path(external_task["cwd"]), external_cwd.resolve())
                    self.assertTrue(external_cwd.exists())
                    self.assertFalse(
                        (
                            horbot_root
                            / "task-workspaces"
                            / "main"
                            / "dm_main"
                            / external_task["id"]
                        ).exists()
                    )

                    external_update_cwd = root / "outside-task-workspace-updated"
                    external_update_response = await client.patch(
                        f"/api/task-workspaces/{task['id']}",
                        json={"cwd": str(external_update_cwd)},
                    )
                    self.assertEqual(external_update_response.status_code, 200)
                    self.assertEqual(Path(external_update_response.json()["cwd"]), external_update_cwd.resolve())
                    self.assertTrue(external_update_cwd.exists())

                    delete_response = await client.delete(f"/api/task-workspaces/{second_task['id']}")
                    self.assertEqual(delete_response.status_code, 200)
                    self.assertEqual(delete_response.json()["task_id"], second_task["id"])

                    deleted_get_response = await client.get(f"/api/task-workspaces/{second_task['id']}")
                    self.assertEqual(deleted_get_response.status_code, 404)

                    missing_delete_response = await client.delete("/api/task-workspaces/not-found")
                    self.assertEqual(missing_delete_response.status_code, 404)

    async def test_filters_by_agent_id(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            horbot_root = root / ".horbot"
            workspace_root = root / "agents"
            config = Config()
            config.agents.defaults.workspace = str(workspace_root / "main")
            config.agents.instances = {
                "main": AgentConfig(id="main", name="Main", is_main=True, workspace=str(workspace_root / "main")),
                "writer": AgentConfig(id="writer", name="Writer", workspace=str(workspace_root / "writer")),
            }
            config = normalize_config(config)

            manager = get_agent_manager()
            with (
                patch.dict("os.environ", {"HORBOT_ROOT": str(horbot_root)}),
                patch("horbot.web.security.get_cached_config", return_value=config),
                patch("horbot.web.api.get_cached_config", return_value=config),
                patch("horbot.agent.manager.get_cached_config", return_value=config),
                patch("horbot.config.loader.get_cached_config", return_value=config),
            ):
                manager.reload(config)
                transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 43123))
                async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                    await client.post(
                        "/api/task-workspaces",
                        json={"title": "Main task", "agent_id": "main", "conversation_id": "dm_main"},
                    )
                    await client.post(
                        "/api/task-workspaces",
                        json={"title": "Writer task", "agent_id": "writer", "conversation_id": "dm_writer"},
                    )

                    response = await client.get("/api/task-workspaces?agent_id=writer")
                    self.assertEqual(response.status_code, 200)
                    tasks = response.json()["task_workspaces"]
                    self.assertEqual(len(tasks), 1)
                    self.assertEqual(tasks[0]["title"], "Writer task")
