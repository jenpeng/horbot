"""CLI commands for horbot."""

import asyncio
import os
import signal
from pathlib import Path
import select
import sys

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout

from horbot import __version__, __logo__
from horbot.config.schema import Config

app = typer.Typer(
    name="horbot",
    help=f"{__logo__} horbot - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

# ---------------------------------------------------------------------------
# CLI input: prompt_toolkit for editing, paste, history, and display
# ---------------------------------------------------------------------------

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    # Save terminal state so we can restore it on exit
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".horbot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,   # Enter submits (single line mode)
    )


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(f"[cyan]{__logo__} horbot[/cyan]")
    console.print(body)
    console.print()


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Read user input using prompt_toolkit (handles paste, history, display).

    prompt_toolkit natively handles:
    - Multiline paste (bracketed paste mode)
    - History navigation (up/down arrows)
    - Clean display (no ghost characters or artifacts)
    """
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>You:</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc



def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} horbot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """horbot - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize horbot configuration and workspace."""
    from horbot.config.loader import get_config_path, load_config, save_config
    from horbot.config.schema import Config
    from horbot.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        console.print("  [bold]y[/bold] = overwrite with defaults (existing values will be lost)")
        console.print("  [bold]N[/bold] = refresh config, keeping existing values and adding new fields")
        if typer.confirm("Overwrite?"):
            config = Config()
            save_config(config)
            console.print(f"[green]✓[/green] Config reset to defaults at {config_path}")
        else:
            config = load_config()
            save_config(config)
            console.print(f"[green]✓[/green] Config refreshed at {config_path} (existing values preserved)")
    else:
        save_config(Config())
        console.print(f"[green]✓[/green] Created config at {config_path}")
    
    # Create workspace
    workspace = get_workspace_path()
    
    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created workspace at {workspace}")
    
    # Create default bootstrap files
    _create_workspace_templates(workspace)
    
    console.print(f"\n{__logo__} horbot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.horbot/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]horbot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See the chat apps section in the project README.[/dim]")




def _create_workspace_templates(workspace: Path):
    """Create default workspace template files from bundled templates."""
    from importlib.resources import files as pkg_files
    import locale
    import os
    
    templates_dir = pkg_files("horbot") / "templates"
    
    # Detect system language
    system_lang = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "") or locale.getdefaultlocale()[0] or ""
    use_chinese = system_lang.startswith("zh") or "zh_CN" in system_lang or "zh_TW" in system_lang
    
    for item in templates_dir.iterdir():
        if not item.name.endswith(".md"):
            continue
        
        # Skip Chinese templates in the iteration (they'll be used as alternatives)
        if item.name.endswith("_ZH.md"):
            continue
        
        # For SOUL.md and USER.md, use Chinese version if system is Chinese
        if item.name in ("SOUL.md", "USER.md") and use_chinese:
            zh_template_name = item.name.replace(".md", "_ZH.md")
            zh_template = templates_dir / zh_template_name
            if zh_template.is_file():
                dest = workspace / item.name
                if not dest.exists():
                    dest.write_text(zh_template.read_text(encoding="utf-8"), encoding="utf-8")
                    console.print(f"  [dim]Created {item.name} (中文版)[/dim]")
                continue
        
        dest = workspace / item.name
        if not dest.exists():
            dest.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
            console.print(f"  [dim]Created {item.name}[/dim]")

    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)

    memory_template = templates_dir / "memory" / "MEMORY.md"
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text(memory_template.read_text(encoding="utf-8"), encoding="utf-8")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")

    history_file = memory_dir / "HISTORY.md"
    if not history_file.exists():
        history_file.write_text("", encoding="utf-8")
        console.print("  [dim]Created memory/HISTORY.md[/dim]")

    (workspace / "skills").mkdir(exist_ok=True)


def _make_provider(config: Config):
    """Create the appropriate LLM provider from config."""
    from horbot.providers.litellm_provider import LiteLLMProvider
    from horbot.providers.openai_codex_provider import OpenAICodexProvider
    from horbot.providers.custom_provider import CustomProvider
    from horbot.providers.base import LLMProvider, LLMResponse

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    # OpenAI Codex (OAuth)
    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        return OpenAICodexProvider(default_model=model)

    # Custom: direct OpenAI-compatible endpoint, bypasses LiteLLM
    if provider_name == "custom":
        return CustomProvider(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
        )

    from horbot.providers.registry import find_by_name
    spec = find_by_name(provider_name)
    if not model.startswith("bedrock/") and not (p and p.api_key) and not (spec and spec.is_oauth):
        # Return a dummy provider that will error when used
        class DummyProvider(LLMProvider):
            async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
                raise ValueError("No API key configured. Set one in ~/.horbot/config.json under providers section")
            def get_default_model(self):
                return model
        return DummyProvider()

    from horbot.utils.paths import get_uploads_dir
    upload_dir = str(get_uploads_dir())
    
    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
        upload_dir=upload_dir,
    )


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    dev: bool = typer.Option(False, "--dev", "-d", help="Development mode with auto-reload"),
):
    """Start the horbot gateway."""
    if dev:
        _run_gateway_dev(port, verbose)
    else:
        _run_gateway(port, verbose)


def _run_gateway_dev(port: int, verbose: bool) -> None:
    """Run gateway in development mode with auto-reload."""
    try:
        import watchfiles
    except ImportError:
        console.print("[red]Error: watchfiles not installed. Install with: pip install watchfiles[/red]")
        return
    
    import subprocess
    import sys
    
    def run_server():
        cmd = [sys.executable, "-m", "horbot", "gateway", "--port", str(port)]
        if verbose:
            cmd.append("--verbose")
        return subprocess.Popen(cmd)
    
    console.print("[yellow]🔧 Development mode: Auto-reload enabled[/yellow]")
    console.print("[dim]Watching for file changes...[/dim]")
    
    process = run_server()
    
    def on_change(changes):
        nonlocal process
        console.print("\n[yellow]📝 File changed, restarting...[/yellow]")
        process.terminate()
        process.wait()
        process = run_server()
    
    try:
        watchfiles.watch(
            on_change,
            ".",
            target_cls=watchfiles.PythonFilter,
            ignore_permission_denied=True,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping...[/yellow]")
        process.terminate()
        process.wait()


def _run_gateway(port: int, verbose: bool) -> None:
    """Run gateway in production mode."""
    import uvicorn
    from horbot.config.loader import load_config
    from horbot.bus.queue import MessageBus
    from horbot.agent.loop import AgentLoop
    from horbot.agent.manager import get_agent_manager
    from horbot.channels.manager import ChannelManager
    from horbot.channels.endpoints import get_default_agent_id
    from horbot.gateway.http_api import build_gateway_http_app
    from horbot.session.manager import SessionManager
    from horbot.cron.service import CronService
    from horbot.cron.types import CronJob
    from horbot.utils.helpers import get_cron_store_path
    from horbot.heartbeat.service import HeartbeatService
    from horbot.utils.paths import get_uploads_dir
    from horbot.providers.registry import create_provider

    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    console.print(f"{__logo__} Starting horbot gateway on port {port}...")
    
    config = load_config()
    bus = MessageBus()
    agent_manager = get_agent_manager()
    agent_manager.reload(config)
    upload_dir = str(get_uploads_dir())
    
    # Create cron service first (callback set after agent creation)
    cron_store_path = get_cron_store_path()
    cron = CronService(cron_store_path)

    def _build_agent_loop(agent_id: str) -> AgentLoop:
        agent_instance = agent_manager.get_agent(agent_id)
        if agent_instance is None:
            raise RuntimeError(f"Agent '{agent_id}' not found")

        agent_config = agent_instance.config
        model_name = agent_instance.model
        explicit_provider_name = (
            agent_config.provider
            if agent_config.provider and agent_config.provider != "auto"
            else None
        )
        provider_name = explicit_provider_name or config.get_provider_name(model_name)
        provider_config = (
            getattr(config.providers, provider_name, None)
            if provider_name
            else None
        )

        if not model_name:
            raise RuntimeError(f"Agent '{agent_id}' has no model configured")
        if not provider_name or provider_config is None:
            raise RuntimeError(f"Agent '{agent_id}' has no provider configured")

        provider = create_provider(
            provider_name,
            api_key=getattr(provider_config, "api_key", None),
            api_base=getattr(provider_config, "api_base", None),
            extra_headers=getattr(provider_config, "extra_headers", None),
            default_model=model_name,
            upload_dir=upload_dir,
        )

        return AgentLoop(
            bus=bus,
            provider=provider,
            workspace=agent_instance.get_workspace(),
            model=model_name,
            temperature=config.agents.defaults.temperature,
            max_tokens=config.agents.defaults.max_tokens,
            max_iterations=config.agents.defaults.max_tool_iterations,
            memory_window=config.agents.defaults.memory_window,
            brave_api_key=config.tools.web.search.api_key or None,
            exec_config=config.tools.exec,
            cron_service=cron,
            restrict_to_workspace=config.tools.restrict_to_workspace,
            session_manager=SessionManager(agent_instance.get_sessions_dir()),
            mcp_servers=config.tools.mcp_servers,
            channels_config=config.channels,
            system_prompt=agent_config.system_prompt or None,
            personality=agent_config.personality or None,
            agent_id=agent_instance.id,
            agent_name=agent_instance.name,
            team_ids=agent_instance.teams,
        )

    configured_agent_ids = agent_manager.list_agent_ids()
    if not configured_agent_ids:
        raise RuntimeError("No agents configured. Please create at least one agent first.")

    agent_loops: dict[str, AgentLoop] = {
        agent_id: _build_agent_loop(agent_id)
        for agent_id in configured_agent_ids
    }
    default_agent_id = get_default_agent_id(config) or configured_agent_ids[0]
    default_agent = agent_loops[default_agent_id]

    async def _dispatch_to_agent(agent: AgentLoop, msg) -> None:
        try:
            response = await agent.process_message(msg)
            if response is not None:
                response.channel_instance_id = response.channel_instance_id or msg.channel_instance_id
                response.target_agent_id = response.target_agent_id or agent._agent_id
                await bus.publish_outbound(response)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            console.print(f"[red]Agent dispatch failed for {agent._agent_id}: {exc}[/red]")
            from horbot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                channel_instance_id=msg.channel_instance_id,
                target_agent_id=agent._agent_id,
                content="Sorry, I encountered an error.",
                metadata=msg.metadata or {},
            ))

    async def _route_inbound_messages() -> None:
        while True:
            msg = await bus.consume_inbound()
            target_agent_id = msg.target_agent_id or default_agent_id
            agent = agent_loops.get(target_agent_id, default_agent)
            if msg.content.strip().lower() == "/stop":
                await agent._handle_stop(msg)
                continue
            task = asyncio.create_task(_dispatch_to_agent(agent, msg))
            agent._active_tasks.setdefault(msg.session_key, []).append(task)
            task.add_done_callback(
                lambda t, a=agent, k=msg.session_key: (
                    a._active_tasks.get(k, []) and a._active_tasks[k].remove(t)
                    if t in a._active_tasks.get(k, [])
                    else None
                )
            )
    
    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        response = await default_agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        if job.payload.deliver and job.payload.to:
            from horbot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                target_agent_id=default_agent_id,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job
    
    # Create channel manager
    channels = ChannelManager(config, bus)
    gateway_app = build_gateway_http_app(channels)
    gateway_server = uvicorn.Server(
        uvicorn.Config(
            gateway_app,
            host=config.gateway.host,
            port=port,
            log_level="info" if verbose else "warning",
            access_log=verbose,
        )
    )

    def _pick_heartbeat_target() -> tuple[str, str, str | None]:
        """Pick a routable channel/chat target for heartbeat-triggered messages."""
        from horbot.utils.helpers import parse_session_key_with_known_routes

        enabled = set(channels.enabled_channels)
        for agent in agent_loops.values():
            for item in agent.sessions.list_sessions():
                key = item.get("key") or ""
                if ":" not in key:
                    continue
                endpoint_id, chat_id = parse_session_key_with_known_routes(
                    key,
                    known_route_keys=enabled,
                )
                if endpoint_id in {"cli", "system"}:
                    continue
                if endpoint_id not in enabled or not chat_id:
                    continue
                channel = channels.get_channel(endpoint_id)
                if channel is not None:
                    return channel.name, chat_id, endpoint_id
        return "cli", "direct", None

    # Create heartbeat service
    async def on_heartbeat_execute(tasks: str) -> str:
        """Phase 2: execute heartbeat tasks through the full agent loop."""
        channel, chat_id, _channel_instance_id = _pick_heartbeat_target()

        async def _silent(*_args, **_kwargs):
            pass

        return await default_agent.process_direct(
            tasks,
            session_key="heartbeat",
            channel=channel,
            chat_id=chat_id,
            on_progress=_silent,
        )

    async def on_heartbeat_notify(response: str) -> None:
        """Deliver a heartbeat response to the user's channel."""
        from horbot.bus.events import OutboundMessage
        channel, chat_id, channel_instance_id = _pick_heartbeat_target()
        if channel == "cli":
            return  # No external channel available to deliver to
        await bus.publish_outbound(OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            channel_instance_id=channel_instance_id,
            target_agent_id=default_agent_id,
            content=response,
        ))

    hb_cfg = config.gateway.heartbeat
    # Only enable heartbeat if provider is not a dummy
    try:
        # Test if provider is functional
        loop = asyncio.get_event_loop()
        loop.run_until_complete(default_agent.provider.chat([{"role": "user", "content": "test"}]))
        heartbeat_enabled = hb_cfg.enabled
    except Exception:
        # Provider is not configured, disable heartbeat
        heartbeat_enabled = False
        console.print("[yellow]Warning: No API key configured, heartbeat disabled[/yellow]")

    heartbeat = HeartbeatService(
        workspace=default_agent.workspace,
        provider=default_agent.provider,
        model=default_agent.model,
        on_execute=on_heartbeat_execute,
        on_notify=on_heartbeat_notify,
        interval_s=hb_cfg.interval_s,
        enabled=heartbeat_enabled,
    )
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")
    
    console.print(f"[green]✓[/green] Heartbeat: every {hb_cfg.interval_s}s")
    
    async def run():
        gateway_task = None
        try:
            await cron.start()
            await heartbeat.start()
            for agent in agent_loops.values():
                await agent._connect_mcp()
            gateway_task = asyncio.create_task(gateway_server.serve())
            await asyncio.gather(
                _route_inbound_messages(),
                channels.start_all(),
                gateway_task,
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
        finally:
            gateway_server.should_exit = True
            if gateway_task is not None:
                gateway_task.cancel()
                await asyncio.gather(gateway_task, return_exceptions=True)
            for agent in agent_loops.values():
                await agent.close_mcp()
            heartbeat.stop()
            cron.stop()
            for agent in agent_loops.values():
                agent.stop()
            await channels.stop_all()
    
    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show horbot runtime logs during chat"),
):
    """Interact with the agent directly."""
    from horbot.config.loader import load_config
    from horbot.bus.queue import MessageBus
    from horbot.agent.loop import AgentLoop
    from horbot.cron.service import CronService
    from horbot.utils.helpers import get_cron_store_path
    from loguru import logger
    
    config = load_config()
    
    bus = MessageBus()
    provider = _make_provider(config)

    # Create cron service for tool usage (no callback needed for CLI unless running)
    cron_store_path = get_cron_store_path()
    cron = CronService(cron_store_path)

    if logs:
        logger.enable("horbot")
    else:
        logger.disable("horbot")
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
    )
    
    # Show spinner when logs are off (no output to miss); skip when logs are on
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        # Animated spinner is safe to use with prompt_toolkit input handling
        return console.status("[dim]horbot is thinking...[/dim]", spinner="dots")

    async def _cli_progress(content: str, *, tool_hint: bool = False) -> None:
        ch = agent_loop.channels_config
        if ch and tool_hint and not ch.send_tool_hints:
            return
        if ch and not tool_hint and not ch.send_progress:
            return
        console.print(f"  [dim]↳ {content}[/dim]")

    if message:
        # Single message mode — direct call, no bus needed
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id, on_progress=_cli_progress)
            _print_agent_response(response, render_markdown=markdown)
            await agent_loop.close_mcp()

        asyncio.run(run_once())
    else:
        # Interactive mode — route through bus like other channels
        from horbot.bus.events import InboundMessage
        _init_prompt_session()
        console.print(f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n")

        if ":" in session_id:
            cli_channel, cli_chat_id = session_id.split(":", 1)
        else:
            cli_channel, cli_chat_id = "cli", session_id

        def _exit_on_sigint(signum, frame):
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)

        async def run_interactive():
            bus_task = asyncio.create_task(agent_loop.run())
            turn_done = asyncio.Event()
            turn_done.set()
            turn_response: list[str] = []

            async def _consume_outbound():
                while True:
                    try:
                        msg = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
                        if msg.metadata.get("_progress"):
                            is_tool_hint = msg.metadata.get("_tool_hint", False)
                            ch = agent_loop.channels_config
                            if ch and is_tool_hint and not ch.send_tool_hints:
                                pass
                            elif ch and not is_tool_hint and not ch.send_progress:
                                pass
                            else:
                                console.print(f"  [dim]↳ {msg.content}[/dim]")
                        elif not turn_done.is_set():
                            if msg.content:
                                turn_response.append(msg.content)
                            turn_done.set()
                        elif msg.content:
                            console.print()
                            _print_agent_response(msg.content, render_markdown=markdown)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        break

            outbound_task = asyncio.create_task(_consume_outbound())

            try:
                while True:
                    try:
                        _flush_pending_tty_input()
                        user_input = await _read_interactive_input_async()
                        command = user_input.strip()
                        if not command:
                            continue

                        if _is_exit_command(command):
                            _restore_terminal()
                            console.print("\nGoodbye!")
                            break

                        turn_done.clear()
                        turn_response.clear()

                        await bus.publish_inbound(InboundMessage(
                            channel=cli_channel,
                            sender_id="user",
                            chat_id=cli_chat_id,
                            content=user_input,
                        ))

                        with _thinking_ctx():
                            await turn_done.wait()

                        if turn_response:
                            _print_agent_response(turn_response[0], render_markdown=markdown)
                    except KeyboardInterrupt:
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
                    except EOFError:
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
            finally:
                agent_loop.stop()
                outbound_task.cancel()
                await asyncio.gather(bus_task, outbound_task, return_exceptions=True)
                await agent_loop.close_mcp()

        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from horbot.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )

    # Feishu
    fs = config.channels.feishu
    fs_config = f"app_id: {fs.app_id[:10]}..." if fs.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "Feishu",
        "✓" if fs.enabled else "✗",
        fs_config
    )

    # Mochat
    mc = config.channels.mochat
    mc_base = mc.base_url or "[dim]not configured[/dim]"
    table.add_row(
        "Mochat",
        "✓" if mc.enabled else "✗",
        mc_base
    )
    
    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    # Slack
    slack = config.channels.slack
    slack_config = "socket" if slack.app_token and slack.bot_token else "[dim]not configured[/dim]"
    table.add_row(
        "Slack",
        "✓" if slack.enabled else "✗",
        slack_config
    )

    # DingTalk
    dt = config.channels.dingtalk
    dt_config = f"client_id: {dt.client_id[:10]}..." if dt.client_id else "[dim]not configured[/dim]"
    table.add_row(
        "DingTalk",
        "✓" if dt.enabled else "✗",
        dt_config
    )

    # QQ
    qq = config.channels.qq
    qq_config = f"app_id: {qq.app_id[:10]}..." if qq.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "QQ",
        "✓" if qq.enabled else "✗",
        qq_config
    )

    # Email
    em = config.channels.email
    em_config = em.imap_host if em.imap_host else "[dim]not configured[/dim]"
    table.add_row(
        "Email",
        "✓" if em.enabled else "✗",
        em_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess
    
    # User's bridge location
    user_bridge = Path.home() / ".horbot" / "bridge"

    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge
    if (legacy_user_bridge / "dist" / "index.js").exists():
        return legacy_user_bridge
    
    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)
    
    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # horbot/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)
    
    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge
    
    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall horbot-ai")
        raise typer.Exit(1)
    
    console.print(f"{__logo__} Setting up bridge...")
    
    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))
    
    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)
    
    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess
    from horbot.config.loader import load_config
    
    config = load_config()
    bridge_dir = _get_bridge_dir()
    
    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")
    
    env = {**os.environ}
    if config.channels.whatsapp.bridge_token:
        env["BRIDGE_TOKEN"] = config.channels.whatsapp.bridge_token
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True, env=env)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from horbot.cron.service import CronService
    from horbot.utils.helpers import get_cron_store_path
    
    store_path = get_cron_store_path()
    service = CronService(store_path)
    
    jobs = service.list_jobs(include_disabled=all)
    
    if not jobs:
        console.print("No scheduled jobs.")
        return
    
    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")
    
    import time
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = f"{job.schedule.expr or ''} ({job.schedule.tz})" if job.schedule.tz else (job.schedule.expr or "")
        else:
            sched = "one-time"
        
        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            ts = job.state.next_run_at_ms / 1000
            try:
                tz = ZoneInfo(job.schedule.tz) if job.schedule.tz else None
                next_run = _dt.fromtimestamp(ts, tz).strftime("%Y-%m-%d %H:%M")
            except Exception:
                next_run = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        
        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"
        
        table.add_row(job.id, job.name, sched, status, next_run)
    
    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    tz: str | None = typer.Option(None, "--tz", help="IANA timezone for cron (e.g. 'America/Vancouver')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"),
):
    """Add a scheduled job."""
    from horbot.cron.service import CronService
    from horbot.cron.types import CronSchedule
    from horbot.utils.helpers import get_cron_store_path
    
    if tz and not cron_expr:
        console.print("[red]Error: --tz can only be used with --cron[/red]")
        raise typer.Exit(1)

    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)
    
    store_path = get_cron_store_path()
    service = CronService(store_path)
    
    try:
        job = service.add_job(
            name=name,
            schedule=schedule,
            message=message,
            deliver=deliver,
            to=to,
            channel=channel,
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e

    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from horbot.cron.service import CronService
    from horbot.utils.helpers import get_cron_store_path
    
    store_path = get_cron_store_path()
    service = CronService(store_path)
    
    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from horbot.cron.service import CronService
    from horbot.utils.helpers import get_cron_store_path
    
    store_path = get_cron_store_path()
    service = CronService(store_path)
    
    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from loguru import logger
    from horbot.config.loader import load_config
    from horbot.cron.service import CronService
    from horbot.cron.types import CronJob
    from horbot.bus.queue import MessageBus
    from horbot.agent.loop import AgentLoop
    from horbot.utils.helpers import get_cron_store_path
    logger.disable("horbot")

    config = load_config()
    provider = _make_provider(config)
    bus = MessageBus()
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
    )

    store_path = get_cron_store_path()
    service = CronService(store_path)

    result_holder = []

    async def on_job(job: CronJob) -> str | None:
        response = await agent_loop.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        result_holder.append(response)
        return response

    service.on_job = on_job

    async def run():
        return await service.run_job(job_id, force=force)

    if asyncio.run(run()):
        console.print("[green]✓[/green] Job executed")
        if result_holder:
            _print_agent_response(result_holder[0], render_markdown=True)
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show horbot status."""
    from horbot.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} horbot Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from horbot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")
        
        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_oauth:
                console.print(f"{spec.label}: [green]✓ (OAuth)[/green]")
            elif spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}")


# ============================================================================
# OAuth Login
# ============================================================================

provider_app = typer.Typer(help="Manage providers")
app.add_typer(provider_app, name="provider")


_LOGIN_HANDLERS: dict[str, callable] = {}


def _register_login(name: str):
    def decorator(fn):
        _LOGIN_HANDLERS[name] = fn
        return fn
    return decorator


@provider_app.command("login")
def provider_login(
    provider: str = typer.Argument(..., help="OAuth provider (e.g. 'openai-codex', 'github-copilot')"),
):
    """Authenticate with an OAuth provider."""
    from horbot.providers.registry import PROVIDERS

    key = provider.replace("-", "_")
    spec = next((s for s in PROVIDERS if s.name == key and s.is_oauth), None)
    if not spec:
        names = ", ".join(s.name.replace("_", "-") for s in PROVIDERS if s.is_oauth)
        console.print(f"[red]Unknown OAuth provider: {provider}[/red]  Supported: {names}")
        raise typer.Exit(1)

    handler = _LOGIN_HANDLERS.get(spec.name)
    if not handler:
        console.print(f"[red]Login not implemented for {spec.label}[/red]")
        raise typer.Exit(1)

    console.print(f"{__logo__} OAuth Login - {spec.label}\n")
    handler()


@_register_login("openai_codex")
def _login_openai_codex() -> None:
    try:
        from oauth_cli_kit import get_token, login_oauth_interactive
        token = None
        try:
            token = get_token()
        except Exception:
            pass
        if not (token and token.access):
            console.print("[cyan]Starting interactive OAuth login...[/cyan]\n")
            token = login_oauth_interactive(
                print_fn=lambda s: console.print(s),
                prompt_fn=lambda s: typer.prompt(s),
            )
        if not (token and token.access):
            console.print("[red]✗ Authentication failed[/red]")
            raise typer.Exit(1)
        console.print(f"[green]✓ Authenticated with OpenAI Codex[/green]  [dim]{token.account_id}[/dim]")
    except ImportError:
        console.print("[red]oauth_cli_kit not installed. Run: pip install oauth-cli-kit[/red]")
        raise typer.Exit(1)


@_register_login("github_copilot")
def _login_github_copilot() -> None:
    import asyncio

    console.print("[cyan]Starting GitHub Copilot device flow...[/cyan]\n")

    async def _trigger():
        from litellm import acompletion
        await acompletion(model="github_copilot/gpt-4o", messages=[{"role": "user", "content": "hi"}], max_tokens=1)

    try:
        asyncio.run(_trigger())
        console.print("[green]✓ Authenticated with GitHub Copilot[/green]")
    except Exception as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)


# ============================================================================
# Web Server Commands
# ============================================================================


@app.command()
def web(
    port: int = typer.Option(8000, "--port", "-p", help="Backend server port"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Web server host"),
    frontend_port: int = typer.Option(3000, "--frontend-port", "-f", help="Frontend dev server port"),
):
    """Start the horbot web server with hot reload enabled by default.
    
    This starts both:
    - Backend server (port 8000) with Python hot reload
    - Frontend dev server (port 3000) with Vite HMR
    """
    import uvicorn
    import subprocess
    import signal
    import sys
    from pathlib import Path
    
    console.print(f"{__logo__} Starting horbot web server with hot reload...")
    console.print(f"[green]Backend:[/green] http://{host}:{port} (with hot reload)")
    console.print(f"[green]Frontend:[/green] http://localhost:{frontend_port} (with HMR)")
    console.print("")
    console.print("[yellow]Press Ctrl+C to stop both servers[/yellow]")
    
    frontend_dir = Path(__file__).parent.parent / "web" / "frontend"
    
    frontend_process = None
    
    def signal_handler(sig, frame):
        console.print("\n[yellow]Stopping servers...[/yellow]")
        if frontend_process:
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_process.kill()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if (frontend_dir / "package.json").exists():
        console.print(f"[blue]Starting frontend dev server on port {frontend_port}...[/blue]")
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(frontend_port)],
            cwd=str(frontend_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        console.print("[yellow]Warning: Frontend directory not found, skipping frontend server[/yellow]")
    
    try:
        uvicorn.run(
            "horbot.web.main:app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=[str(Path(__file__).parent.parent)],
        )
    finally:
        if frontend_process:
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_process.kill()


if __name__ == "__main__":
    app()
