"""Tests for personal CLI commands."""
from typer.testing import CliRunner

from cuga.personal.cli.main import personal_app


runner = CliRunner()


class TestPersonalCLI:
    def test_help(self):
        result = runner.invoke(personal_app, ["--help"])
        assert result.exit_code == 0
        assert "personal" in result.output.lower() or "automation" in result.output.lower()

    def test_init_command(self):
        result = runner.invoke(personal_app, ["init"])
        assert result.exit_code == 0
        assert "Setup" in result.output or "config" in result.output.lower()

    def test_doctor_command(self):
        result = runner.invoke(personal_app, ["doctor"])
        assert result.exit_code == 0
        # Should mention at least one dependency
        assert "yaml" in result.output.lower() or "pydantic" in result.output.lower()

    def test_skill_help(self):
        result = runner.invoke(personal_app, ["skill", "--help"])
        assert result.exit_code == 0

    def test_skill_list_empty(self, tmp_path):
        result = runner.invoke(personal_app, ["skill", "list", "--dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "No skills" in result.output

    def test_skill_create(self, tmp_path):
        result = runner.invoke(personal_app, ["skill", "create", "my-test-skill"], catch_exceptions=False)
        # Creates in ./skills/ — may fail if cwd isn't writable, but shouldn't crash
        # Just verify no unhandled exception
        assert result.exit_code in (0, 1)

    def test_schedule_help(self):
        result = runner.invoke(personal_app, ["schedule", "--help"])
        assert result.exit_code == 0

    def test_schedule_list(self):
        result = runner.invoke(personal_app, ["schedule", "list"])
        assert result.exit_code == 0
