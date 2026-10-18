"""Path resolution: repo root, runtime home, vault and project directories."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Optional

_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parent.parent.parent  # scripts/lib/paths.py -> repo root


def repo_root() -> Path:
    return REPO_ROOT


def runtime_home() -> Path:
    """Where learned data lives: ``$RESEARCH_OS_HOME`` or the XDG config dir."""
    env = os.environ.get("RESEARCH_OS_HOME")
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "deep-research-os"


def runtime_learning_dir() -> Path:
    return runtime_home() / "learning"


def capabilities_dir() -> Path:
    return runtime_learning_dir() / "capabilities"


def archive_dir() -> Path:
    return runtime_learning_dir() / "archive"


def seed_runtime() -> None:
    """Copy the repo's seeded ``learnings/`` into the runtime home (once).

    Never overwrites existing runtime data. Called by ``doctor`` and ``init``.
    """
    src = REPO_ROOT / "learnings"
    dst = runtime_learning_dir()
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def vault_dir(override: Optional[str] = None) -> Path:
    """The research vault — where projects live.

    Priority: explicit override -> ``$RESEARCH_OS_VAULT`` -> ``./research-os`` in cwd.
    """
    if override:
        return Path(override).expanduser().resolve()
    env = os.environ.get("RESEARCH_OS_VAULT")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / "research-os").resolve()


def projects_dir(vault: Optional[str] = None) -> Path:
    return vault_dir(vault) / "projects"


def project_dir(slug: str, vault: Optional[str] = None) -> Path:
    return projects_dir(vault) / slug


def resolve_project(slug: Optional[str] = None, vault: Optional[str] = None) -> Path:
    """Find a project dir: by slug, or the newest one when slug is omitted."""
    root = projects_dir(vault)
    if slug:
        p = root / slug
        if not p.exists():
            raise FileNotFoundError(f"project '{slug}' not found under {root}")
        return p
    if not root.exists():
        raise FileNotFoundError(
            "no projects found — run `research_ctl.py init \"question\"` first"
        )
    candidates = [d for d in root.iterdir() if (d / "state.json").exists()]
    if not candidates:
        raise FileNotFoundError(f"no initialized projects under {root}")
    if len(candidates) == 1:
        return candidates[0]
    return max(candidates, key=lambda d: (d / "state.json").stat().st_mtime)


def state_path(project: Path) -> Path:
    return project / "state.json"


def load_state(project: Path) -> dict:
    with open(state_path(project), encoding="utf-8") as fh:
        return json.load(fh)


def save_state(project: Path, state: dict) -> None:
    tmp = state_path(project).with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
    tmp.replace(state_path(project))
