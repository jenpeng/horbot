import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from horbot.agent.context import ContextBuilder
from horbot.agent.manager import AgentInstance, AgentManager
from horbot.channels.endpoints import legacy_endpoint_id, list_channel_endpoints
from horbot.config.loader import invalidate_config_cache, save_config
from horbot.config.normalizer import normalize_config, set_agent_team_memberships, set_team_members
from horbot.config.schema import AgentConfig, ChannelEndpointConfig, Config, TeamConfig
from horbot.workspace.manager import WorkspaceManager


class ConfigNormalizerTests(unittest.TestCase):
    def setUp(self) -> None:
        WorkspaceManager._instance = None
        AgentManager._instance = None

    def tearDown(self) -> None:
        invalidate_config_cache()
        WorkspaceManager._instance = None
        AgentManager._instance = None

    def test_normalize_config_does_not_materialize_default_agent_when_instances_empty(self):
        config = Config()

        normalize_config(config)

        self.assertEqual(config.agents.instances, {})

    def test_normalize_config_merges_agent_and_team_memberships(self):
        config = Config()
        config.agents.instances = {
            "main": AgentConfig(id="main", name="Main", is_main=True, teams=["alpha"]),
            "writer": AgentConfig(id="writer", name="Writer"),
        }
        config.teams.instances = {
            "alpha": TeamConfig(id="alpha", name="Alpha", members=["writer", "missing"]),
        }

        normalize_config(config)

        self.assertEqual(config.teams.instances["alpha"].members, ["writer", "main"])
        self.assertEqual(config.agents.instances["main"].teams, ["alpha"])
        self.assertEqual(config.agents.instances["writer"].teams, ["alpha"])

    def test_normalize_config_clears_legacy_main_agent_flags(self):
        config = Config()
        config.agents.instances = {
            "main": AgentConfig(id="main", name="Main", is_main=True),
            "worker": AgentConfig(id="worker", name="Worker", is_main=True),
        }

        normalize_config(config)

        self.assertFalse(config.agents.instances["main"].is_main)
        self.assertFalse(config.agents.instances["worker"].is_main)

    def test_authoritative_sync_helpers_replace_old_memberships(self):
        config = Config()
        config.agents.instances = {
            "main": AgentConfig(id="main", name="Main", is_main=True, teams=["alpha"]),
            "writer": AgentConfig(id="writer", name="Writer", teams=["alpha"]),
        }
        config.teams.instances = {
            "alpha": TeamConfig(id="alpha", name="Alpha", members=["main", "writer"]),
            "beta": TeamConfig(id="beta", name="Beta", members=[]),
        }

        set_agent_team_memberships(config, "writer", ["beta"])
        set_team_members(config, "alpha", ["main"])

        self.assertEqual(config.agents.instances["writer"].teams, ["beta"])
        self.assertEqual(config.teams.instances["alpha"].members, ["main"])
        self.assertEqual(config.teams.instances["beta"].members, ["writer"])

    def test_workspace_manager_uses_agent_and_team_workspace_overrides(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            config = Config()
            config.agents.defaults.workspace = str(root / ".horbot" / "agents" / "main" / "workspace")
            config.agents.instances = {
                "main": AgentConfig(id="main", name="Main", is_main=True),
                "writer": AgentConfig(id="writer", name="Writer", workspace=str(root / "custom-agent-ws")),
            }
            config.teams.instances = {
                "alpha": TeamConfig(id="alpha", name="Alpha", workspace=str(root / "custom-team-ws")),
            }

            import horbot.config.loader as loader

            loader._cached_config = normalize_config(config)
            manager = WorkspaceManager.get_instance()

            agent_ws = manager.get_agent_workspace("writer")
            team_ws = manager.get_team_workspace("alpha")

            self.assertEqual(Path(agent_ws.workspace_path).resolve(), (root / "custom-agent-ws").resolve())
            self.assertTrue((root / "custom-agent-ws" / ".horbot-agent" / "memory").exists())
            self.assertEqual(Path(team_ws.workspace_path).resolve(), (root / "custom-team-ws").resolve())
            self.assertTrue((root / "custom-team-ws" / ".horbot-team" / "shared_memory").exists())

    def test_main_agent_overrides_do_not_mutate_global_defaults(self):
        config = Config()
        config.agents.defaults.models.main.model = "openai/gpt-4o-mini"
        config.agents.defaults.models.main.provider = "openai"
        config.agents.defaults.workspace = "/tmp/default-workspace"
        config.agents.instances = {
            "main": AgentConfig(
                id="main",
                name="Main",
                is_main=True,
                model="anthropic/claude-sonnet-4-20250514",
                provider="anthropic",
                workspace="/tmp/main-agent-workspace",
            )
        }

        normalize_config(config)

        self.assertEqual(config.agents.defaults.models.main.model, "openai/gpt-4o-mini")
        self.assertEqual(config.agents.defaults.models.main.provider, "openai")
        self.assertEqual(config.agents.defaults.workspace, "/tmp/default-workspace")
        self.assertEqual(config.agents.instances["main"].model, "anthropic/claude-sonnet-4-20250514")
        self.assertEqual(config.agents.instances["main"].provider, "anthropic")
        self.assertEqual(config.agents.instances["main"].workspace, "/tmp/main-agent-workspace")

    def test_save_config_preserves_defaults_when_main_agent_has_override(self):
        config = Config()
        config.agents.defaults.models.main.model = "gpt-5.4"
        config.agents.defaults.models.main.provider = "mycc"
        config.agents.instances = {
            "main": AgentConfig(
                id="main",
                name="Main",
                is_main=True,
                model="MiniMax-M2.7",
                provider="minimax",
            )
        }

        with tempfile.TemporaryDirectory() as tempdir:
            output_path = Path(tempdir) / "config.json"
            save_config(config, output_path)
            saved = Config.model_validate_json(output_path.read_text(encoding="utf-8"))

        self.assertEqual(saved.agents.defaults.models.main.provider, "mycc")
        self.assertEqual(saved.agents.defaults.models.main.model, "gpt-5.4")
        self.assertEqual(saved.agents.instances["main"].provider, "minimax")
        self.assertEqual(saved.agents.instances["main"].model, "MiniMax-M2.7")

    def test_agent_instance_requires_explicit_model_configuration(self):
        config = Config()
        config.agents.defaults.models.main.model = "openai/gpt-4o-mini"
        config.agents.defaults.models.main.provider = "openai"
        config.providers.openai.api_key = "test-key"
        import horbot.config.loader as loader

        loader._cached_config = normalize_config(config)

        instance = AgentInstance(AgentConfig(id="writer", name="Writer"))

        self.assertEqual(instance.model, "")
        self.assertEqual(instance.provider, "")
        self.assertTrue(instance.setup_required)

    def test_workspace_manager_uses_main_agent_workspace_for_custom_main_agent(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            config = Config()
            config.agents.instances = {
                "captain": AgentConfig(id="captain", name="Captain", is_main=True),
            }

            import horbot.config.loader as loader

            loader._cached_config = normalize_config(config)
            with patch.dict(os.environ, {"HORBOT_ROOT": str(root / ".horbot")}, clear=False):
                manager = WorkspaceManager.get_instance()
                main_ws = manager.get_agent_workspace("captain")

            self.assertEqual(
                Path(main_ws.workspace_path).resolve(),
                (root / ".horbot" / "agents" / "captain" / "workspace").resolve(),
            )
            self.assertEqual(
                Path(main_ws.memory_path).resolve(),
                (root / ".horbot" / "agents" / "captain" / "memory").resolve(),
            )

    def test_workspace_manager_resolves_relative_horbot_override_from_project_root(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            config = Config()
            config.agents.defaults.workspace = ".horbot/agents/main/workspace"
            config.agents.instances = {
                "main": AgentConfig(id="main", name="Main", is_main=True, workspace=".horbot/agents/main/workspace"),
            }

            import horbot.config.loader as loader

            loader._cached_config = normalize_config(config)
            manager = WorkspaceManager.get_instance()

            with patch.dict(os.environ, {"HORBOT_ROOT": str(root / ".horbot")}, clear=False), patch.object(Config, "_find_project_root", return_value=root):
                main_ws = manager.get_agent_workspace("main")

            resolved_workspace = Path(main_ws.workspace_path).resolve()
            self.assertEqual(resolved_workspace, (root / ".horbot" / "agents" / "main" / "workspace").resolve())
            self.assertTrue((resolved_workspace / ".horbot-agent" / "memory").exists())

    def test_config_workspace_path_defaults_to_horbot_default_workspace(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            config = Config()

            with patch.dict(os.environ, {"HORBOT_ROOT": str(root / ".horbot")}, clear=False):
                self.assertEqual(
                    config.workspace_path.resolve(),
                    (root / ".horbot" / "agents" / "default" / "workspace").resolve(),
                )

    def test_config_workspace_path_uses_custom_main_agent_when_defaults_empty(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            config = Config()
            config.agents.instances = {
                "captain": AgentConfig(id="captain", name="Captain", is_main=True),
            }

            with patch.dict(os.environ, {"HORBOT_ROOT": str(root / ".horbot")}, clear=False):
                self.assertEqual(
                    config.workspace_path.resolve(),
                    (root / ".horbot" / "agents" / "captain" / "workspace").resolve(),
                )

    def test_agent_manager_does_not_create_ghost_main_for_custom_main_agent(self):
        config = Config()
        config.agents.instances = {
            "captain": AgentConfig(id="captain", name="Captain", is_main=True),
        }

        import horbot.config.loader as loader

        loader._cached_config = normalize_config(config)
        manager = AgentManager.get_instance()
        manager.reload(loader._cached_config)

        self.assertEqual({agent.id for agent in manager.get_all_agents()}, {"captain"})
        self.assertEqual(manager.get_default_agent().id, "captain")
        self.assertEqual(manager.get_agent("main").id, "captain")

    def test_normalize_config_prunes_team_member_profiles_for_missing_members(self):
        config = Config()
        config.agents.instances = {
            "writer": AgentConfig(id="writer", name="Writer"),
        }
        config.teams.instances = {
            "alpha": TeamConfig(
                id="alpha",
                name="Alpha",
                members=["writer", "missing"],
                member_profiles={
                    "writer": {"role": "lead", "responsibility": "coordinate", "priority": 1, "isLead": True},
                    "missing": {"role": "ghost", "responsibility": "ghost", "priority": 9},
                },
            ),
        }

        normalize_config(config)

        self.assertEqual(config.teams.instances["alpha"].members, ["writer"])
        self.assertEqual(set(config.teams.instances["alpha"].member_profiles.keys()), {"writer"})

    def test_normalize_config_syncs_channel_endpoint_bindings(self):
        config = Config()
        config.agents.instances = {
            "alpha": AgentConfig(id="alpha", name="Alpha", channel_bindings=["legacy:telegram"]),
            "beta": AgentConfig(id="beta", name="Beta", channel_bindings=["sales-feishu"]),
        }
        config.channels.endpoints = [
            ChannelEndpointConfig(
                id="sales-feishu",
                type="feishu",
                name="Sales Feishu",
                agent_id="alpha",
                enabled=True,
            ),
            ChannelEndpointConfig(
                id="sales-feishu",
                type="feishu",
                name="Duplicated",
                agent_id="beta",
                enabled=True,
            ),
        ]

        normalize_config(config)

        self.assertEqual(len(config.channels.endpoints), 1)
        self.assertEqual(config.channels.endpoints[0].agent_id, "alpha")
        self.assertEqual(config.agents.instances["alpha"].channel_bindings, ["legacy:telegram", "sales-feishu"])
        self.assertEqual(config.agents.instances["beta"].channel_bindings, [])

    def test_list_channel_endpoints_projects_legacy_and_custom_configs(self):
        config = Config()
        config.agents.instances = {
            "alpha": AgentConfig(id="alpha", name="Alpha", channel_bindings=[legacy_endpoint_id("telegram"), "sales-feishu"]),
        }
        config.channels.telegram.enabled = True
        config.channels.telegram.token = "telegram-token"
        config.channels.endpoints = [
            ChannelEndpointConfig(
                id="sales-feishu",
                type="feishu",
                name="Sales Feishu",
                agent_id="alpha",
                enabled=True,
                config={"app_id": "cli_xxx", "app_secret": "secret"},
            ),
        ]

        normalize_config(config)
        endpoints = {endpoint.id: endpoint for endpoint in list_channel_endpoints(config)}

        self.assertEqual(set(endpoints.keys()), {legacy_endpoint_id("telegram"), "sales-feishu"})
        self.assertEqual(endpoints[legacy_endpoint_id("telegram")].agent_id, "alpha")
        self.assertEqual(endpoints[legacy_endpoint_id("telegram")].status, "ready")
        self.assertEqual(endpoints["sales-feishu"].status, "ready")
        self.assertEqual(endpoints["sales-feishu"].type, "feishu")


class ContextBuilderBootstrapTests(unittest.TestCase):
    def tearDown(self) -> None:
        invalidate_config_cache()
        WorkspaceManager._instance = None
        AgentManager._instance = None

    def test_bootstrap_files_use_agent_local_user_profile(self):
        with tempfile.TemporaryDirectory() as tempdir:
            workspace = Path(tempdir)
            (workspace / "SOUL.md").write_text("# Local Soul\n", encoding="utf-8")
            (workspace / "USER.md").write_text("# Local User\npreferred_language: zh-CN\n", encoding="utf-8")

            builder = ContextBuilder(workspace=workspace, use_hierarchical=False, agent_name="Local")
            bootstrap = builder._load_bootstrap_files()

            self.assertIn("Local Soul", bootstrap)
            self.assertIn("Local User", bootstrap)


if __name__ == "__main__":
    unittest.main()
