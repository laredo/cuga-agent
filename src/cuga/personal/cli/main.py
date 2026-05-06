"""CUGA Personal CLI — main Typer app and top-level commands."""

import os

import typer

from cuga.personal.cli.skill_commands import skill_app
from cuga.personal.cli.schedule_commands import schedule_app

personal_app = typer.Typer(help="CUGA Personal — Enterprise Business Automation Assistant")
personal_app.add_typer(skill_app, name="skill")
personal_app.add_typer(schedule_app, name="schedule")


@personal_app.command()
def init():
    """Interactive setup wizard: configure LLM endpoint, Slack, and skill directories."""
    typer.echo("CUGA Personal Setup Wizard")
    typer.echo("-" * 40)
    typer.echo("Configuration via environment variables:")
    typer.echo("  LLM:    set your provider env vars (e.g. OPENAI_API_KEY, WATSONX_* etc.)")
    typer.echo("  Slack:  SLACK_BOT_TOKEN, SLACK_APP_TOKEN")
    typer.echo("  Skills: create a ./skills/ directory with skill subdirectories")
    typer.echo("")
    typer.echo("Run 'cuga personal start' once configured.")


def _ensure_backend(host: str = "127.0.0.1") -> None:
    """Start the CUGA backend (registry + demo) if it isn't already running."""
    import socket

    from cuga.config import settings

    registry_port = settings.server_ports.registry
    demo_port = settings.server_ports.demo

    def _port_open(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) == 0

    if _port_open(registry_port) and _port_open(demo_port):
        typer.echo(f"Backend already running (registry:{registry_port}, demo:{demo_port})")
        return

    typer.echo("Starting CUGA backend (registry + knowledge)…")

    from cuga.cli.main import _make_app_manager, kill_processes_by_port, wait_for_server
    from cuga.backend.server.demo_manage_setup import setup_demo_manage_config
    from cuga.backend.server.managed_mcp import ensure_managed_mcp_file_exists, get_managed_mcp_path

    os.environ["CUGA_DEMO_MODE"] = "knowledge"
    os.environ["CUGA_DEMO_ADVANCED"] = "true"
    os.environ["CUGA_MANAGER_MODE"] = "true"
    os.environ["DYNACONF_POLICY__FILESYSTEM_SYNC"] = "false"
    os.environ["MCP_SERVERS_FILE"] = "none"
    os.environ["DYNACONF_KNOWLEDGE__ENABLED"] = "true"
    os.environ["DYNACONF_KNOWLEDGE__AGENT_LEVEL_ENABLED"] = "true"
    os.environ["DYNACONF_KNOWLEDGE__SESSION_LEVEL_ENABLED"] = "true"
    os.environ["CUGA_HOST"] = host

    ensure_managed_mcp_file_exists(get_managed_mcp_path())
    setup_demo_manage_config("demo_knowledge")

    app_mgr = _make_app_manager()
    kill_processes_by_port([registry_port, demo_port])

    registry_proc = app_mgr.start_registry(host)
    if registry_proc is None or registry_proc.poll() is not None:
        typer.echo("Error: registry failed to start.", err=True)
        raise typer.Exit(1)
    wait_for_server(registry_port, "Registry")

    demo_proc = app_mgr.start_demo(host)
    if demo_proc is None or demo_proc.poll() is not None:
        typer.echo("Error: demo server failed to start.", err=True)
        raise typer.Exit(1)
    wait_for_server(demo_port, "Knowledge backend")

    typer.echo(f"Backend ready — registry:{registry_port}, demo:{demo_port}")


@personal_app.command()
def start(
    skill_dirs: list[str] = typer.Option(
        ["./skills", "~/.cuga/skills"],
        "--skill-dir",
        "-s",
        help="Directories to scan for skills",
    ),
    channel: str = typer.Option(
        None,
        help="Channel to use: cli | slack. Defaults to slack if SLACK_BOT_TOKEN is set, else cli.",
    ),
    no_backend: bool = typer.Option(
        False,
        "--no-backend",
        help="Skip auto-starting the CUGA backend (use if already running).",
    ),
):
    """Start the personal agent (gateway + scheduler + skills)."""
    import asyncio

    resolved_channel = channel or ("slack" if os.environ.get("SLACK_BOT_TOKEN") else "cli")

    if not no_backend:
        _ensure_backend()

    async def _run():
        from cuga.personal.gateway.session import SessionManager
        from cuga.personal.skills.loader import SkillLoader
        from cuga.personal.skills.dispatcher import SkillDispatcher
        from cuga.personal.scheduler.engine import SchedulerEngine
        from cuga.personal.core.orchestrator import PersonalAgentOrchestrator

        session_manager = SessionManager()
        skill_loader = SkillLoader(skill_dirs)
        skills = await skill_loader.scan()
        loaded = [await skill_loader.load(s.name) for s in skills]
        skill_dispatcher = SkillDispatcher(skills=loaded)

        typer.echo(f"Loaded {len(loaded)} skill(s): {[s.metadata.name for s in loaded]}")

        if resolved_channel == "slack":
            bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
            app_token = os.environ.get("SLACK_APP_TOKEN", "")
            signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")

            if not bot_token:
                typer.echo("Error: SLACK_BOT_TOKEN is not set.", err=True)
                raise typer.Exit(1)
            if not app_token:
                typer.echo("Error: SLACK_APP_TOKEN is not set (required for Socket Mode).", err=True)
                raise typer.Exit(1)

            from cuga.personal.gateway.adapters.slack import SlackAdapter

            adapter = SlackAdapter(
                bot_token=bot_token,
                app_token=app_token,
                signing_secret=signing_secret or None,
            )
            scheduler = SchedulerEngine(
                storage=None,
                session_manager=session_manager,
                skill_loader=skill_loader,
                gateway=adapter,
                check_interval=30,
            )
            orch = PersonalAgentOrchestrator(
                session_manager=session_manager,
                skill_loader=skill_loader,
                skill_dispatcher=skill_dispatcher,
                gateway=adapter,
                scheduler=scheduler,
            )
            typer.echo("Starting CUGA Personal in Slack (Socket Mode)…")
            await orch.start()

        else:
            from cuga.personal.gateway.adapters.cli import CLIAdapter

            adapter = CLIAdapter()
            scheduler = SchedulerEngine(
                storage=None,
                session_manager=session_manager,
                skill_loader=skill_loader,
                gateway=adapter,
                check_interval=30,
            )
            orch = PersonalAgentOrchestrator(
                session_manager=session_manager,
                skill_loader=skill_loader,
                skill_dispatcher=skill_dispatcher,
                gateway=adapter,
                scheduler=scheduler,
            )
            typer.echo("Starting CUGA Personal in CLI mode…")
            await orch.start()

    asyncio.run(_run())


@personal_app.command()
def doctor():
    """Diagnose configuration and connectivity issues."""
    import importlib

    checks = [
        ("croniter", "Scheduler (cron expression parsing)"),
        ("yaml", "YAML parsing (pyyaml)"),
        ("pydantic", "Data models (pydantic)"),
    ]
    all_ok = True
    for module, label in checks:
        try:
            importlib.import_module(module)
            typer.echo(f"  [OK]  {label}")
        except ImportError:
            typer.echo(f"  [MISSING] {label} — install cuga[personal]")
            all_ok = False

    try:
        import slack_bolt  # noqa: F401

        typer.echo("  [OK]  Slack adapter (slack_bolt)")
    except ImportError:
        typer.echo("  [OPTIONAL] Slack adapter — install cuga[personal] for Slack support")

    slack_token = os.environ.get("SLACK_BOT_TOKEN", "")
    slack_app_token = os.environ.get("SLACK_APP_TOKEN", "")
    if slack_token and slack_app_token:
        typer.echo("  [OK]  Slack tokens found (Socket Mode ready)")
    elif slack_token:
        typer.echo("  [WARN] SLACK_BOT_TOKEN set but SLACK_APP_TOKEN missing (required for Socket Mode)")
    else:
        typer.echo("  [INFO] No Slack tokens — will run in CLI mode")

    if all_ok:
        typer.echo("\nAll required dependencies are installed.")
    else:
        typer.echo("\nSome dependencies are missing. Run: pip install cuga[personal]")
