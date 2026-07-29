from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from debugging_engine import __version__
from debugging_engine.cli import app
from debugging_engine.integrations.registry import AGENTS, get_agent, parse_agent_keys
from debugging_engine.integrations.scaffold import ScaffoldError, scaffold_agent, uninstall_agent

runner = CliRunner()

SKILL_FILES = {
    "debugging-engine-investigate": ("SKILL.md", "reference.md", "examples.md"),
    "debugging-engine-incident": ("SKILL.md",),
    "debugging-engine-performance": ("SKILL.md",),
}


@pytest.mark.parametrize("agent_key", sorted(AGENTS))
def test_scaffold_agent_writes_skills(tmp_path: Path, agent_key: str):
    result = scaffold_agent(agent_key, tmp_path, force=False)
    agent = get_agent(agent_key)
    assert result["agent"] == agent_key
    assert result["version"] == __version__
    skill_root = tmp_path / agent.skill_root
    for skill, files in SKILL_FILES.items():
        for name in files:
            path = skill_root / skill / name
            assert path.is_file(), path
            assert path.stat().st_size > 0
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8").find(".debugging-engine/") >= 0
    manifest = json.loads((tmp_path / ".debugging-engine" / "integration.json").read_text(encoding="utf-8"))
    assert manifest["agent"] == agent_key
    assert manifest["debugging_engine_version"] == __version__


def test_scaffold_refuses_overwrite_without_force(tmp_path: Path):
    scaffold_agent("claude", tmp_path, force=False)
    skill = tmp_path / ".claude/skills/debugging-engine-investigate/SKILL.md"
    skill.write_text("modified locally\n", encoding="utf-8")
    with pytest.raises(ScaffoldError, match="--force"):
        scaffold_agent("claude", tmp_path, force=False)


def test_scaffold_force_overwrites(tmp_path: Path):
    scaffold_agent("cursor", tmp_path, force=False)
    skill = tmp_path / ".cursor/skills/debugging-engine-investigate/SKILL.md"
    skill.write_text("modified locally\n", encoding="utf-8")
    scaffold_agent("cursor", tmp_path, force=True)
    assert "Debugging Engine Investigate" in skill.read_text(encoding="utf-8")


def test_scaffold_unknown_agent(tmp_path: Path):
    with pytest.raises(KeyError, match="Unknown agent"):
        scaffold_agent("nope", tmp_path)


def test_templates_packaged():
    from debugging_engine.integrations.scaffold import templates_root

    root = templates_root()
    assert (root / "debugging-engine-investigate" / "SKILL.md").is_file()


def test_cli_agent_scaffolds(tmp_path: Path):
    result = runner.invoke(app, ["--agent", "codex", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".agents/skills/debugging-engine-investigate/SKILL.md").is_file()
    payload = json.loads(result.stdout)
    assert payload["agent"] == "codex"


def test_cli_unknown_agent(tmp_path: Path):
    result = runner.invoke(app, ["--agent", "nope", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "Supported agents" in result.output


def test_cli_help_still_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "open" in result.output
    assert "--agent" in result.output


def test_repo_cursor_skills_match_templates():
    """This repo's .cursor/skills/ stay in sync with packaged templates."""
    repo = Path(__file__).resolve().parents[1]
    from debugging_engine.integrations.scaffold import templates_root

    templates = templates_root()
    for skill, files in SKILL_FILES.items():
        for name in files:
            expected = (templates / skill / name).read_text(encoding="utf-8")
            actual = (repo / ".cursor" / "skills" / skill / name).read_text(encoding="utf-8")
            assert actual == expected, f"{skill}/{name} out of sync with package templates"


def test_uninstall_removes_matching_skills(tmp_path: Path):
    scaffold_agent("claude", tmp_path, force=False)
    cases = tmp_path / ".debugging-engine" / "cases"
    cases.mkdir(parents=True)
    (cases / "keep.txt").write_text("case data\n", encoding="utf-8")
    gitignore_before = (tmp_path / ".gitignore").read_text(encoding="utf-8")

    result = uninstall_agent("claude", tmp_path, force=False)
    assert result["manifest_removed"] is True
    assert not (tmp_path / ".claude/skills/debugging-engine-investigate").exists()
    assert not (tmp_path / ".debugging-engine" / "integration.json").exists()
    assert (cases / "keep.txt").read_text(encoding="utf-8") == "case data\n"
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == gitignore_before


def test_uninstall_preserves_modified_without_force(tmp_path: Path):
    scaffold_agent("cursor", tmp_path, force=False)
    skill = tmp_path / ".cursor/skills/debugging-engine-investigate/SKILL.md"
    skill.write_text("modified locally\n", encoding="utf-8")
    result = uninstall_agent("cursor", tmp_path, force=False)
    assert skill.is_file()
    assert "modified locally" in skill.read_text(encoding="utf-8")
    assert any(p.endswith("SKILL.md") for p in result["preserved"])
    # unmodified companion files removed
    assert not (tmp_path / ".cursor/skills/debugging-engine-investigate/reference.md").exists()


def test_uninstall_force_removes_modified(tmp_path: Path):
    scaffold_agent("copilot", tmp_path, force=False)
    skill = tmp_path / ".github/skills/debugging-engine-investigate/SKILL.md"
    skill.write_text("modified locally\n", encoding="utf-8")
    result = uninstall_agent("copilot", tmp_path, force=True)
    assert result["force"] is True
    assert not (tmp_path / ".github/skills/debugging-engine-investigate").exists()
    assert result["preserved"] == []


def test_cli_agent_uninstall(tmp_path: Path):
    runner.invoke(app, ["--agent", "claude", "--path", str(tmp_path)])
    result = runner.invoke(app, ["--uninstall", "claude", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["agent"] == "claude"
    assert payload["manifest_removed"] is True
    assert not (tmp_path / ".claude/skills/debugging-engine-investigate").exists()


def test_cli_uninstall_requires_value(tmp_path: Path):
    result = runner.invoke(app, ["--uninstall", "--path", str(tmp_path)])
    assert result.exit_code != 0


def test_uninstall_cli_success(monkeypatch):
    monkeypatch.setattr("debugging_engine.cli.shutil.which", lambda _: "/usr/bin/uv")

    class FakeCompleted:
        returncode = 0
        stdout = "Uninstalled: debugging-engine\n"
        stderr = ""

    monkeypatch.setattr(
        "debugging_engine.cli.subprocess.run",
        lambda *args, **kwargs: FakeCompleted(),
    )
    result = runner.invoke(app, ["uninstall-cli"])
    assert result.exit_code == 0
    assert "Uninstalled" in result.output


def test_uninstall_cli_uv_missing(monkeypatch):
    monkeypatch.setattr("debugging_engine.cli.shutil.which", lambda _: None)
    result = runner.invoke(app, ["uninstall-cli"])
    assert result.exit_code == 1
    assert "uv tool uninstall debugging-engine" in result.output


def test_parse_agent_keys_comma_and_all():
    assert parse_agent_keys("claude, cursor") == ["claude", "cursor"]
    assert parse_agent_keys("all") == sorted(AGENTS)
    assert parse_agent_keys("claude,claude") == ["claude"]


def test_parse_agent_keys_rejects_all_mixed():
    with pytest.raises(ValueError, match="Do not mix"):
        parse_agent_keys("all,claude")


def test_parse_agent_keys_unknown():
    with pytest.raises(KeyError, match="Unknown agent"):
        parse_agent_keys("claude,nope")


def test_cli_multi_agent_uninstall(tmp_path: Path):
    runner.invoke(app, ["--agent", "claude,cursor", "--path", str(tmp_path)])
    assert (tmp_path / ".claude/skills/debugging-engine-investigate/SKILL.md").is_file()
    assert (tmp_path / ".cursor/skills/debugging-engine-investigate/SKILL.md").is_file()

    result = runner.invoke(
        app, ["--uninstall", "claude,cursor", "--path", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["agents"] == ["claude", "cursor"]
    assert "results" in payload
    assert not (tmp_path / ".claude/skills/debugging-engine-investigate").exists()
    assert not (tmp_path / ".cursor/skills/debugging-engine-investigate").exists()


def test_cli_all_uninstall(tmp_path: Path):
    runner.invoke(app, ["--agent", "all", "--path", str(tmp_path)])
    result = runner.invoke(app, ["--uninstall", "all", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert set(payload["agents"]) == set(AGENTS)
    for key, spec in AGENTS.items():
        assert not (tmp_path / spec.skill_root / "debugging-engine-investigate").exists(), key


def test_cli_invalid_multi_agent(tmp_path: Path):
    result = runner.invoke(app, ["--agent", "claude,nope", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "Supported agents" in result.output


def test_cli_all_mixed_rejected(tmp_path: Path):
    result = runner.invoke(app, ["--uninstall", "all,claude", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "mix" in result.output.lower() or "Do not mix" in result.output


def test_cli_single_uninstall_shape_unchanged(tmp_path: Path):
    runner.invoke(app, ["--agent", "codex", "--path", str(tmp_path)])
    result = runner.invoke(app, ["--uninstall", "codex", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["agent"] == "codex"
    assert "agents" not in payload
    assert "manifest_removed" in payload


def test_cli_agent_and_uninstall_mutually_exclusive(tmp_path: Path):
    result = runner.invoke(
        app, ["--agent", "claude", "--uninstall", "claude", "--path", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "either --agent or --uninstall" in result.output
