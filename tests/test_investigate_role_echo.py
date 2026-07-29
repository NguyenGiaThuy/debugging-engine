"""Investigate-skill workflow on session_ttl: every role must be announced."""

from __future__ import annotations

from pathlib import Path

from debugging_engine.application.service import CaseService
from debugging_engine.domain.models import AgentRole
from debugging_engine.runtime.stubs.fixture import materialize_session_ttl, session_ttl_issue
from debugging_engine.runtime.stubs.role_announce import (
    REQUIRED_INVESTIGATE_ROLES,
    format_role_announcement,
    roles_from_announcements,
)
from debugging_engine.runtime.stubs.session_ttl_investigate import run_session_ttl_investigate


def session_ttl_workspace(tmp_path: Path) -> tuple[Path, Path]:
    workspace = materialize_session_ttl(tmp_path / "session_ttl")
    return workspace, session_ttl_issue(workspace)


def test_format_role_announcement_matches_skill():
    line = format_role_announcement(
        {"role": "Analyst", "objective": "Propose hypotheses and experiments."}
    )
    assert line == "**Role: Analyst** — Propose hypotheses and experiments."


def test_session_ttl_investigate_announces_all_roles(tmp_path: Path):
    """Run the full investigate loop on a non-obvious TTL bug; require every role in chat."""
    workspace, issue = session_ttl_workspace(tmp_path)
    svc = CaseService(repo_root=workspace, store_root=tmp_path / "cases")
    result = run_session_ttl_investigate(svc, issue)

    assert result["status"] == "RESOLVED"
    assert result["root_cause_hypothesis_id"]

    announcements = result["announcements"]
    assert announcements, "expected chat role announcements"

    # Every announcement must use the skill-visible format.
    for line in announcements:
        assert line.startswith("**Role: "), line
        assert " — " in line, line

    found = roles_from_announcements(announcements)
    required = {r.value for r in REQUIRED_INVESTIGATE_ROLES}
    missing = required - found
    assert not missing, (
        f"Missing role announcements: {sorted(missing)}. "
        f"Seen: {result['roles_seen']}. Lines:\n" + "\n".join(announcements)
    )

    # Order sanity: Analyst before Adversary before first Judge approve path;
    # Implementer and Verifier both appear (fix path needs both).
    assert AgentRole.ANALYST.value in result["roles_seen"]
    assert AgentRole.ADVERSARY.value in result["roles_seen"]
    assert AgentRole.JUDGE.value in result["roles_seen"]
    assert AgentRole.IMPLEMENTER.value in result["roles_seen"]
    assert AgentRole.VERIFIER.value in result["roles_seen"]

    # Fixed file landed and tests would pass (already verified inside driver).
    fixed = (workspace / "session.py").read_text(encoding="utf-8")
    assert "last_seen" in fixed
    assert "created_at) <= self._ttl" not in fixed.replace(" ", "")


def test_session_ttl_fixture_is_initially_failing(tmp_path: Path):
    """Seeded bug is not trivially green before investigation."""
    import subprocess
    import sys

    workspace, _ = session_ttl_workspace(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_session.py", "-q"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "failed" in (proc.stdout + proc.stderr).lower() or proc.returncode != 0
