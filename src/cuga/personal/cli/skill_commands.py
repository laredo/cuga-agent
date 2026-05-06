"""CLI commands for managing skills."""
import typer
from pathlib import Path

skill_app = typer.Typer(help="Manage CUGA Personal skills")


@skill_app.command("list")
def list_skills(
    skill_dirs: list[str] = typer.Option(
        ["./skills", "~/.cuga/skills"],
        "--dir", "-d",
        help="Directories to scan for skills",
    )
):
    """List all installed skills."""
    import asyncio
    from cuga.personal.skills.loader import SkillLoader

    async def _run():
        loader = SkillLoader(skill_dirs)
        skills = await loader.scan()
        if not skills:
            typer.echo("No skills found.")
            return
        typer.echo(f"{'Name':<25} {'Version':<10} {'Commands'}")
        typer.echo("-" * 60)
        for s in skills:
            cmds = ", ".join(s.commands) if s.commands else "(no commands)"
            typer.echo(f"{s.name:<25} {s.version:<10} {cmds}")

    asyncio.run(_run())


@skill_app.command()
def install(source: str = typer.Argument(..., help="Path or URL to the skill directory")):
    """Install a skill from a local path."""
    src = Path(source).expanduser()
    if not src.exists():
        typer.echo(f"Error: path not found: {source}", err=True)
        raise typer.Exit(1)
    if not (src / "SKILL.md").exists():
        typer.echo(f"Error: no SKILL.md found in {source}", err=True)
        raise typer.Exit(1)
    # For now, just validate — Phase 2 will copy to ~/.cuga/skills/
    typer.echo(f"Skill found at {source}. Use --skill-dir to point CUGA Personal at this path.")


@skill_app.command()
def create(name: str = typer.Argument(..., help="Name of the new skill (kebab-case)")):
    """Scaffold a new skill directory."""
    dest = Path(".") / "skills" / name
    if dest.exists():
        typer.echo(f"Error: {dest} already exists", err=True)
        raise typer.Exit(1)
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: \"TODO: describe what this skill does\"\nversion: \"0.1.0\"\ncommands: [\"/{name}\"]\ntriggers: []\n---\n\n# {name}\n\nTODO: document your skill here.\n"
    )
    (dest / "policies").mkdir()
    (dest / "knowledge").mkdir()
    typer.echo(f"Skill scaffolded at {dest}")
    typer.echo(f"Edit {dest}/SKILL.md to configure it.")


@skill_app.command()
def test(name: str = typer.Argument(..., help="Skill name to test")):
    """Run tests for a skill (placeholder)."""
    typer.echo(f"Running tests for skill: {name}")
    typer.echo("(Skill-specific tests not yet implemented)")
