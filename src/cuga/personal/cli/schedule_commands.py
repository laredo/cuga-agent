"""CLI commands for managing scheduled automations."""

import typer
from typing import Optional

schedule_app = typer.Typer(help="Manage scheduled automations")


@schedule_app.command("list")
def list_jobs():
    """List all scheduled jobs."""
    # In-memory only for now; Phase 2 will load from storage
    typer.echo("No scheduled jobs. Use 'cuga personal schedule create' to add one.")


@schedule_app.command()
def create(
    skill: str = typer.Option(..., help="Skill name to invoke"),
    schedule: str = typer.Option(..., help="Cron expression (e.g. '0 16 * * 5')"),
    prompt: str = typer.Option(..., help="Prompt to send to the skill"),
    name: Optional[str] = typer.Option(None, help="Job name"),
    channel: str = typer.Option("cli", help="Delivery channel (cli|slack)"),
    channel_id: str = typer.Option("cli-session", help="Target channel/session ID"),
):
    """Create a new scheduled job."""
    import uuid
    from datetime import datetime, timezone
    from cuga.personal.scheduler.models import ScheduledJob
    from cuga.personal.gateway.base import DeliveryTarget
    from cuga.personal.scheduler.engine import _next_run

    job = ScheduledJob(
        id=str(uuid.uuid4()),
        name=name or f"{skill} @ {schedule}",
        schedule=schedule,
        skill_name=skill,
        prompt=prompt,
        user_id="cli-user",
        delivery=DeliveryTarget(platform=channel, channel_id=channel_id),
        created_at=datetime.now(timezone.utc),
    )
    next_run = _next_run(schedule)
    typer.echo(f"Job created: {job.name}")
    typer.echo(f"  ID:       {job.id}")
    typer.echo(f"  Skill:    {skill}")
    typer.echo(f"  Schedule: {schedule}")
    typer.echo(f"  Next run: {next_run}")
    typer.echo("\nNote: job persistence requires storage — start 'cuga personal start' to run it.")


@schedule_app.command()
def pause(job_id: str = typer.Argument(..., help="Job ID to pause")):
    """Pause a scheduled job."""
    typer.echo(f"Pausing job {job_id} (requires running agent — see 'cuga personal start')")


@schedule_app.command()
def run(job_id: str = typer.Argument(..., help="Job ID to run immediately")):
    """Run a scheduled job immediately (for testing)."""
    typer.echo(f"Triggering job {job_id} (requires running agent — see 'cuga personal start')")
