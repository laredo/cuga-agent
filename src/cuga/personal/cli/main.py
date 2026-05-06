"""CUGA Personal CLI — main Typer app and top-level commands."""
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


@personal_app.command()
def start(
    skill_dirs: list[str] = typer.Option(
        ["./skills", "~/.cuga/skills"],
        "--skill-dir", "-s",
        help="Directories to scan for skills",
    ),
    channel: str = typer.Option("cli", help="Channel to use: cli | slack"),
):
    """Start the personal agent (gateway + scheduler + skills)."""
    import asyncio

    async def _run():
        from cuga.personal.gateway.session import SessionManager
        from cuga.personal.skills.loader import SkillLoader
        from cuga.personal.skills.dispatcher import SkillDispatcher

        session_manager = SessionManager()
        skill_loader = SkillLoader(skill_dirs)
        skills = await skill_loader.scan()
        loaded = [await skill_loader.load(s.name) for s in skills]
        skill_dispatcher = SkillDispatcher(skills=loaded)

        typer.echo(f"Loaded {len(loaded)} skill(s): {[s.metadata.name for s in loaded]}")

        if channel == "cli":
            from cuga.personal.gateway.adapters.cli import CLIAdapter
            from cuga.personal.core.orchestrator import PersonalAgentOrchestrator

            adapter = CLIAdapter()
            orch = PersonalAgentOrchestrator(
                session_manager=session_manager,
                skill_loader=skill_loader,
                skill_dispatcher=skill_dispatcher,
                gateway=adapter,
            )
            await adapter.start(on_message=orch.handle_message)
        else:
            typer.echo(f"Channel '{channel}' not yet supported. Use 'cli'.")

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

    if all_ok:
        typer.echo("\nAll required dependencies are installed.")
    else:
        typer.echo("\nSome dependencies are missing. Run: pip install cuga[personal]")
