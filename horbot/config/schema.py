"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Literal, Any

from pydantic import BaseModel, Field, ConfigDict, model_validator
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """Base model that accepts both camelCase and snake_case keys."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class WhatsAppConfig(Base):
    """WhatsApp channel configuration."""

    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    bridge_token: str = ""  # Shared token for bridge auth (optional, recommended)
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(Base):
    """Telegram channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames
    proxy: str | None = None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"
    reply_to_message: bool = False  # If true, bot replies quote the original message


class FeishuConfig(Base):
    """Feishu/Lark channel configuration using WebSocket long connection."""

    enabled: bool = False
    app_id: str = ""  # App ID from Feishu Open Platform
    app_secret: str = ""  # App Secret from Feishu Open Platform
    encrypt_key: str = ""  # Encrypt Key for event subscription (optional)
    verification_token: str = ""  # Verification Token for event subscription (optional)
    allow_from: list[str] = Field(default_factory=list)  # Allowed user open_ids
    skip_ssl_verify: bool = True  # Skip SSL verification for proxy/firewall environments


class DingTalkConfig(Base):
    """DingTalk channel configuration using Stream mode."""

    enabled: bool = False
    client_id: str = ""  # AppKey
    client_secret: str = ""  # AppSecret
    allow_from: list[str] = Field(default_factory=list)  # Allowed staff_ids


class DiscordConfig(Base):
    """Discord channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from Discord Developer Portal
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377  # GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT


class MatrixConfig(Base):
    """Matrix (Element) channel configuration."""

    enabled: bool = False
    homeserver: str = "https://matrix.org"
    access_token: str = ""
    user_id: str = ""  # @bot:matrix.org
    device_id: str = ""
    e2ee_enabled: bool = True # Enable Matrix E2EE support (encryption + encrypted room handling).
    sync_stop_grace_seconds: int = 2 # Max seconds to wait for sync_forever to stop gracefully before cancellation fallback.
    max_media_bytes: int = 20 * 1024 * 1024 # Max attachment size accepted for Matrix media handling (inbound + outbound).
    allow_from: list[str] = Field(default_factory=list)
    group_policy: Literal["open", "mention", "allowlist"] = "open"
    group_allow_from: list[str] = Field(default_factory=list)
    allow_room_mentions: bool = False


class EmailConfig(Base):
    """Email channel configuration (IMAP inbound + SMTP outbound)."""

    enabled: bool = False
    consent_granted: bool = False  # Explicit owner permission to access mailbox data

    # IMAP (receive)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True

    # SMTP (send)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: str = ""

    # Behavior
    auto_reply_enabled: bool = True  # If false, inbound email is read but no automatic reply is sent
    poll_interval_seconds: int = 30
    mark_seen: bool = True
    max_body_chars: int = 12000
    subject_prefix: str = "Re: "
    allow_from: list[str] = Field(default_factory=list)  # Allowed sender email addresses


class MochatMentionConfig(Base):
    """Mochat mention behavior configuration."""

    require_in_groups: bool = False


class MochatGroupRule(Base):
    """Mochat per-group mention requirement."""

    require_mention: bool = False


class MochatConfig(Base):
    """Mochat channel configuration."""

    enabled: bool = False
    base_url: str = "https://mochat.io"
    socket_url: str = ""
    socket_path: str = "/socket.io"
    socket_disable_msgpack: bool = False
    socket_reconnect_delay_ms: int = 1000
    socket_max_reconnect_delay_ms: int = 10000
    socket_connect_timeout_ms: int = 10000
    refresh_interval_ms: int = 30000
    watch_timeout_ms: int = 25000
    watch_limit: int = 100
    retry_delay_ms: int = 500
    max_retry_attempts: int = 0  # 0 means unlimited retries
    claw_token: str = ""
    agent_user_id: str = ""
    sessions: list[str] = Field(default_factory=list)
    panels: list[str] = Field(default_factory=list)
    allow_from: list[str] = Field(default_factory=list)
    mention: MochatMentionConfig = Field(default_factory=MochatMentionConfig)
    groups: dict[str, MochatGroupRule] = Field(default_factory=dict)
    reply_delay_mode: str = "non-mention"  # off | non-mention
    reply_delay_ms: int = 120000


class SlackDMConfig(Base):
    """Slack DM policy configuration."""

    enabled: bool = True
    policy: str = "open"  # "open" or "allowlist"
    allow_from: list[str] = Field(default_factory=list)  # Allowed Slack user IDs


class SlackConfig(Base):
    """Slack channel configuration."""

    enabled: bool = False
    mode: str = "socket"  # "socket" supported
    webhook_path: str = "/slack/events"
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-...
    user_token_read_only: bool = True
    reply_in_thread: bool = True
    react_emoji: str = "eyes"
    group_policy: str = "mention"  # "mention", "open", "allowlist"
    group_allow_from: list[str] = Field(default_factory=list)  # Allowed channel IDs if allowlist
    dm: SlackDMConfig = Field(default_factory=SlackDMConfig)


class QQConfig(Base):
    """QQ channel configuration using botpy SDK."""

    enabled: bool = False
    app_id: str = ""  # 机器人 ID (AppID) from q.qq.com
    secret: str = ""  # 机器人密钥 (AppSecret) from q.qq.com
    allow_from: list[str] = Field(default_factory=list)  # Allowed user openids (empty = public access)


class ShareCrmConfig(Base):
    """ShareCRM (纷享销客) channel configuration using SSE + REST."""

    enabled: bool = False
    gateway_base_url: str = "https://open.fxiaoke.com"  # IM Gateway base URL
    app_id: str = ""  # App ID from ShareCRM
    app_secret: str = ""  # App Secret from ShareCRM
    dm_policy: str = "open"  # "open", "pairing", "allowlist", "disabled"
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs for DM
    group_policy: str = "disabled"  # "open", "allowlist", "disabled"
    group_allow_from: list[str] = Field(default_factory=list)  # Allowed group IDs
    text_chunk_limit: int = 4000  # Max characters per message


class ChannelEndpointConfig(Base):
    """Per-agent channel endpoint configuration."""

    id: str = ""
    type: str = ""
    name: str = ""
    agent_id: str = ""
    enabled: bool = True
    allow_from: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class ChannelsConfig(Base):
    """Configuration for chat channels."""

    send_progress: bool = True    # stream agent's text progress to the channel
    send_tool_hints: bool = False  # stream tool-call hints (e.g. read_file("…"))
    endpoints: list[ChannelEndpointConfig] = Field(default_factory=list)
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    mochat: MochatConfig = Field(default_factory=MochatConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    qq: QQConfig = Field(default_factory=QQConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
    sharecrm: ShareCrmConfig = Field(default_factory=ShareCrmConfig)


class ModelConfig(Base):
    """Single model configuration for a specific scenario."""

    provider: str = ""
    model: str = ""
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)


class ModelsConfig(Base):
    """Multi-model configuration for different scenarios."""

    main: ModelConfig = Field(default_factory=ModelConfig)
    planning: ModelConfig = Field(default_factory=ModelConfig)
    file: ModelConfig = Field(default_factory=ModelConfig)
    image: ModelConfig = Field(default_factory=ModelConfig)
    audio: ModelConfig = Field(default_factory=ModelConfig)
    video: ModelConfig = Field(default_factory=ModelConfig)

    @classmethod
    def get_defaults(cls) -> "ModelsConfig":
        """Get default model configurations.
        
        These are used when no configuration is provided in the config file.
        """
        return cls(
            main=ModelConfig(
                provider="openrouter",
                model="anthropic/claude-sonnet-4-20250514",
                description="主模型 - 通用对话"
            ),
            planning=ModelConfig(
                provider="openrouter",
                model="anthropic/claude-sonnet-4-20250514",
                description="计划模型 - 复杂任务规划"
            ),
            file=ModelConfig(
                provider="openrouter",
                model="anthropic/claude-sonnet-4-20250514",
                description="文件处理模型"
            ),
            image=ModelConfig(
                provider="openrouter",
                model="anthropic/claude-sonnet-4-20250514",
                description="图片处理模型",
                capabilities=["vision"]
            ),
            audio=ModelConfig(
                provider="openrouter",
                model="anthropic/claude-sonnet-4-20250514",
                description="音频处理模型",
                capabilities=["audio"]
            ),
            video=ModelConfig(
                provider="openrouter",
                model="anthropic/claude-sonnet-4-20250514",
                description="视频处理模型",
                capabilities=["vision"]
            ),
        )

    def is_empty(self) -> bool:
        """Check if all model configurations are empty."""
        return all(
            not (mc.provider and mc.model)
            for mc in [self.main, self.planning, self.file, self.image, 
                      self.audio, self.video]
        )

    def merge_with_defaults(self) -> "ModelsConfig":
        """Merge current config with defaults for any empty fields."""
        defaults = self.get_defaults()
        if self.is_empty():
            return defaults
        
        result = ModelsConfig()
        for field in ["main", "planning", "file", "image", "audio", "video"]:
            current = getattr(self, field)
            default = getattr(defaults, field)
            if current.provider and current.model:
                setattr(result, field, current)
            else:
                setattr(result, field, default)
        return result


class ContextCompactConfig(Base):
    """Context compression configuration."""

    enabled: bool = True
    max_tokens: int = 100000  # Token threshold to trigger compression
    preserve_recent: int = 10  # Number of recent messages to preserve
    compress_tool_results: bool = True  # Compress tool results to summaries


class AgentDefaults(Base):
    """Default agent configuration."""

    workspace: str = ""  # Empty means use default from paths module
    max_tokens: int = 8192
    temperature: float = 0.1
    max_tool_iterations: int = 40
    memory_window: int = 100
    planning_mode: str = "unified"  # "unified" (single prompt) or "legacy" (three-stage)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    context_compact: ContextCompactConfig = Field(default_factory=ContextCompactConfig)
    
    def get_workspace_path(self) -> Path:
        """Get the workspace path, using default from paths module if not set."""
        if self.workspace:
            return Path(self.workspace).expanduser()
        from horbot.utils.paths import get_workspace_dir
        return get_workspace_dir()

    @property
    def model(self) -> str:
        """Get main model (backward compatibility)."""
        return self.models.main.model

    @property
    def provider(self) -> str:
        """Get main provider (backward compatibility)."""
        return self.models.main.provider

    @property
    def planning_model(self) -> str | None:
        """Get planning model (backward compatibility)."""
        return self.models.planning.model

    @property
    def planning_provider(self) -> str | None:
        """Get planning provider (backward compatibility)."""
        return self.models.planning.provider


class AgentWorkspaceConfig(Base):
    """Agent workspace configuration."""

    workspace_path: str = ""
    memory_path: str = ""
    sessions_path: str = ""
    skills_path: str = ""


class MemoryBankProfileConfig(Base):
    """Agent-specific memory interpretation profile."""

    mission: str = ""
    directives: list[str] = Field(default_factory=list)
    reasoning_style: str = ""


class TeamWorkspaceConfig(Base):
    """Team workspace configuration."""

    workspace_path: str = ""
    shared_memory_path: str = ""
    taskboard_path: str = ""


class AgentConfig(Base):
    """Agent instance configuration."""

    id: str = ""
    name: str = ""
    description: str = ""
    profile: str = ""
    permission_profile: str = ""
    model: str = ""
    provider: str = "auto"
    system_prompt: str = ""
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    workspace: str = ""
    teams: list[str] = Field(default_factory=list)
    channel_bindings: list[str] = Field(default_factory=list)
    is_main: bool = False
    personality: str = ""
    avatar: str = ""
    evolution_enabled: bool = True
    learning_enabled: bool = True
    skill_evolution: dict[str, Any] = Field(default_factory=dict)
    memory_config: dict[str, Any] = Field(default_factory=dict)
    memory_bank_profile: MemoryBankProfileConfig = Field(default_factory=MemoryBankProfileConfig)


class TeamMemberProfile(Base):
    """Per-team metadata for one agent member."""

    role: str = "member"
    responsibility: str = ""
    priority: int = 100
    is_lead: bool = False


class TeamConfig(Base):
    """Team configuration."""

    id: str = ""
    name: str = ""
    description: str = ""
    members: list[str] = Field(default_factory=list)
    member_profiles: dict[str, TeamMemberProfile] = Field(default_factory=dict)
    workspace: str = ""


class AgentsConfig(Base):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)
    instances: dict[str, AgentConfig] = Field(default_factory=dict)


class TeamsConfig(Base):
    """Teams configuration collection."""

    instances: dict[str, TeamConfig] = Field(default_factory=dict)


class ProviderConfig(Base):
    """LLM provider configuration."""

    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None  # Custom headers (e.g. APP-Code for AiHubMix)


class ProvidersConfig(Base):
    """Configuration for LLM providers."""

    custom: ProviderConfig = Field(default_factory=ProviderConfig)  # Any OpenAI-compatible endpoint
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # 阿里云通义千问
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)  # AiHubMix API gateway
    siliconflow: ProviderConfig = Field(default_factory=ProviderConfig)  # SiliconFlow (硅基流动) API gateway
    volcengine: ProviderConfig = Field(default_factory=ProviderConfig)  # VolcEngine (火山引擎) API gateway
    openai_codex: ProviderConfig = Field(default_factory=ProviderConfig)  # OpenAI Codex (OAuth)
    github_copilot: ProviderConfig = Field(default_factory=ProviderConfig)  # Github Copilot (OAuth)

    model_config = ConfigDict(extra="allow")  # Allow dynamic providers

    @model_validator(mode="before")
    @classmethod
    def convert_extra_providers(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        known_fields = {
            "custom", "anthropic", "openai", "openrouter", "deepseek", "groq",
            "zhipu", "dashscope", "vllm", "gemini", "moonshot", "minimax",
            "aihubmix", "siliconflow", "volcengine", "openai_codex", "github_copilot"
        }
        for key, value in data.items():
            if key not in known_fields and isinstance(value, dict):
                data[key] = ProviderConfig(**value)
        return data


class HeartbeatConfig(Base):
    """Heartbeat service configuration."""

    enabled: bool = True
    interval_s: int = 30 * 60  # 30 minutes


class GatewayConfig(Base):
    """Gateway/server configuration."""

    host: str = "127.0.0.1"
    port: int = 18790
    admin_token: str = ""
    allow_remote_without_token: bool = False
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)


class WebSearchConfig(Base):
    """Web search tool configuration."""

    provider: str = "duckduckgo"  # "duckduckgo", "brave", "tavily"
    api_key: str = ""  # API key for brave or tavily
    max_results: int = 5


class WebToolsConfig(Base):
    """Web tools configuration."""

    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(Base):
    """Shell exec tool configuration."""

    timeout: int = 60
    path_append: str = ""


class MCPServerConfig(Base):
    """MCP server connection configuration (stdio or HTTP)."""

    command: str = ""  # Stdio: command to run (e.g. "npx")
    args: list[str] = Field(default_factory=list)  # Stdio: command arguments
    env: dict[str, str] = Field(default_factory=dict)  # Stdio: extra env vars
    url: str = ""  # HTTP: streamable HTTP endpoint URL
    headers: dict[str, str] = Field(default_factory=dict)  # HTTP: Custom HTTP Headers
    tool_timeout: int = 30  # Seconds before a tool call is cancelled


class PermissionConfig(Base):
    """Tool permission configuration."""

    profile: str = "balanced"
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)
    confirm: list[str] = Field(default_factory=list)


class AutonomousConfig(Base):
    """Autonomous execution configuration."""

    enabled: bool = False
    max_plan_steps: int = 10
    step_timeout: int = 300
    total_timeout: int = 3600
    retry_count: int = 3
    retry_delay: int = 5
    confirm_sensitive: bool = True
    sensitive_operations: list[str] = Field(default_factory=lambda: [
        "write_file", "edit_file", "exec", "spawn", "cron"
    ])
    ## protected_paths ： "**/config.json"
    protected_paths: list[str] = Field(default_factory=lambda: [
        "~/.ssh", "~/.env", "**/.env"
    ])



class ToolsConfig(Base):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = True
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)
    permission: PermissionConfig = Field(default_factory=PermissionConfig)


class Config(BaseSettings):
    """Root configuration for horbot."""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    teams: TeamsConfig = Field(default_factory=TeamsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    autonomous: AutonomousConfig = Field(default_factory=AutonomousConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path.
        
        Handles:
        - Absolute paths: used as-is
        - Relative paths: resolved relative to project root
        - Environment variables: expanded
        - User home: expanded (~)
        """
        workspace = self.agents.defaults.workspace.strip()
        if not workspace:
            from horbot.utils.paths import get_agent_workspace_dir

            default_agent_id = next(iter(self.agents.instances.keys()), "default")
            return get_agent_workspace_dir(default_agent_id)

        path = Path(workspace).expanduser()

        if path.is_absolute():
            return path
        
        project_root = self._find_project_root()
        if project_root:
            return (project_root / workspace).resolve()
        
        return path.resolve()
    
    def _find_project_root(self) -> Path | None:
        """Find project root by looking for marker files."""
        from pathlib import Path
        
        # Try current working directory first
        cwd = Path.cwd()
        for marker in [".git", "pyproject.toml", "setup.py", "requirements.txt", ".horbot"]:
            candidate = cwd
            while candidate != candidate.parent:
                if (candidate / marker).exists():
                    return candidate
                candidate = candidate.parent
        
        # Fall back to config directory
        from horbot.config.loader import get_config_path
        config_path = get_config_path()
        if config_path and config_path.exists():
            config_dir = config_path.parent
            for marker in [".git", "pyproject.toml", "setup.py", "requirements.txt", ".horbot"]:
                candidate = config_dir
                while candidate != candidate.parent:
                    if (candidate / marker).exists():
                        return candidate
                    candidate = candidate.parent
            return config_dir
        return None
    
    def workspace_subdir(self, name: str) -> Path:
        """Get a subdirectory path within workspace.
        
        Args:
            name: Subdirectory name (e.g., ".checkpoints", ".state", ".audit")
            
        Returns:
            Path to the subdirectory (created if needed)
        """
        from horbot.utils.helpers import ensure_dir
        return ensure_dir(self.workspace_path / name)

    def _match_provider(self, model: str | None = None) -> tuple["ProviderConfig | None", str | None]:
        """Match provider config and its registry name. Returns (config, spec_name)."""
        from horbot.providers.registry import PROVIDERS

        forced = self.agents.defaults.provider
        if forced != "auto":
            p = getattr(self.providers, forced, None)
            return (p, forced) if p else (None, None)

        model_lower = (model or self.agents.defaults.model).lower()
        model_normalized = model_lower.replace("-", "_")
        model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
        normalized_prefix = model_prefix.replace("-", "_")

        def _kw_matches(kw: str) -> bool:
            kw = kw.lower()
            return kw in model_lower or kw.replace("-", "_") in model_normalized

        # Explicit provider prefix wins — prevents `github-copilot/...codex` matching openai_codex.
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and model_prefix and normalized_prefix == spec.name:
                if spec.is_oauth or p.api_key:
                    return p, spec.name

        # Match by keyword (order follows PROVIDERS registry)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(_kw_matches(kw) for kw in spec.keywords):
                if spec.is_oauth or p.api_key:
                    return p, spec.name

        # Fallback: gateways first, then others (follows registry order)
        # OAuth providers are NOT valid fallbacks — they require explicit model selection
        for spec in PROVIDERS:
            if spec.is_oauth:
                continue
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config (api_key, api_base, extra_headers). Falls back to first available."""
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider (e.g. "deepseek", "openrouter")."""
        _, name = self._match_provider(model)
        return name

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model. Falls back to first available key."""
        p = self.get_provider(model)
        return p.api_key if p else None

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model. Applies default URLs for known gateways."""
        from horbot.providers.registry import find_by_name

        p, name = self._match_provider(model)
        if p and p.api_base:
            return p.api_base
        # Only gateways get a default api_base here. Standard providers
        # (like Moonshot) set their base URL via env vars in _setup_env
        # to avoid polluting the global litellm.api_base.
        if name:
            spec = find_by_name(name)
            if spec and spec.is_gateway and spec.default_api_base:
                return spec.default_api_base
        return None

    def get_model_for_scenario(
        self,
        scenario: str,
        has_image: bool = False,
        has_audio: bool = False,
        has_video: bool = False,
        has_file: bool = False,
        is_planning: bool = False,
    ) -> tuple[str, str]:
        """Get model and provider for a specific scenario.
        
        Args:
            scenario: Scenario type (main, planning, file, image, audio, video)
            has_image: Whether the request includes images
            has_audio: Whether the request includes audio
            has_video: Whether the request includes video
            has_file: Whether the request includes documents
            is_planning: Whether this is a planning request
            
        Returns:
            Tuple of (model_name, provider_name)
        """
        models = self.agents.defaults.models
        if has_image:
            model_config = models.image
        elif has_audio:
            model_config = models.audio
        elif has_video:
            model_config = models.video
        elif has_file:
            model_config = models.file
        elif is_planning:
            model_config = models.planning
        else:
            model_config = models.main
        
        if model_config.provider and model_config.model:
            return model_config.model, model_config.provider
        
        defaults = ModelsConfig.get_defaults()
        default_config = getattr(defaults, "image" if has_image else 
                                 "audio" if has_audio else 
                                 "video" if has_video else 
                                 "file" if has_file else 
                                 "planning" if is_planning else "main")
        return default_config.model, default_config.provider

    model_config = ConfigDict(env_prefix="HORBOT_", env_nested_delimiter="__")
