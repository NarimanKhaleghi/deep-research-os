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


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def guard_output_location(path: Path) -> None:
    """Refuse to create research outputs inside the skill/repo or runtime dirs.

    Research belongs in a user-chosen folder; the skill directory must stay clean
    (only ``~/.config/deep-research-os/`` may hold persistent learning data).
    """
    p = Path(path).expanduser().resolve()
    if is_inside(p, repo_root()):
        raise ValueError(
            f"refusing to put research output inside the skill/repo directory ({repo_root()}). "
            "Pass an explicit destination: `init \"…\" --dir /path/to/your/folder`"
        )
    if is_inside(p, runtime_home()):
        raise ValueError(
            f"refusing to put research output inside the runtime home ({runtime_home()}) — "
            "that folder holds learning data only. Pass `--dir /path/to/your/folder`"
        )


def discover_project(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from ``start`` (default cwd) looking for a project (state.json)."""
    cur = (start or Path.cwd()).resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / "state.json").exists() and (candidate / "sources").is_dir():
            return candidate
    return None


def registry_path() -> Path:
    return runtime_home() / "projects.json"


def load_registry() -> list[dict]:
    try:
        data = json.loads(registry_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries = data.get("projects") if isinstance(data, dict) else data
    return list(entries or [])


def register_project(project: Path) -> None:
    """Remember a project location so later commands find it without env vars."""
    p = Path(project).expanduser().resolve()
    entries = [e for e in load_registry()
               if Path(str(e.get("path", ""))).expanduser().resolve() != p]
    entries.append({"slug": p.name, "path": str(p)})
    entries = entries[-200:]
    try:
        runtime_home().mkdir(parents=True, exist_ok=True)
        registry_path().write_text(
            json.dumps({"projects": entries}, ensure_ascii=False, indent=1),
            encoding="utf-8")
    except OSError:
        pass  # registry is a convenience, never a failure


def resolve_project(slug: Optional[str] = None, vault: Optional[str] = None) -> Path:
    """Find a project dir.

    Priority: explicit slug/path -> ``$RESEARCH_OS_PROJECT`` -> vault lookup ->
    upward discovery from cwd -> registry of ``--dir`` projects.
    Accepts either a slug under ``<vault>/projects`` or a direct filesystem path
    to a project directory.
    """
    if slug:
        direct = Path(slug).expanduser()
        if direct.is_dir() and (direct / "state.json").exists():
            return direct.resolve()
        root = projects_dir(vault)
        p = root / slug
        if not p.exists():
            raise FileNotFoundError(f"project '{slug}' not found under {root}")
        return p

    env_project = os.environ.get("RESEARCH_OS_PROJECT")
    if env_project:
        ep = Path(env_project).expanduser()
        if (ep / "state.json").exists():
            return ep.resolve()
        raise FileNotFoundError(f"$RESEARCH_OS_PROJECT='{env_project}' has no state.json")

    if not vault:
        found = discover_project()
        if found:
            return found

    root = projects_dir(vault)
    if root.exists():
        candidates = [d for d in root.iterdir() if (d / "state.json").exists()]
        if candidates:
            if len(candidates) == 1:
                return candidates[0]
            return max(candidates, key=lambda d: (d / "state.json").stat().st_mtime)

    for entry in reversed(load_registry()):
        p = Path(str(entry.get("path", ""))).expanduser()
        if (p / "state.json").exists():
            return p.resolve()

    raise FileNotFoundError(
        "no projects found — run `research_ctl.py init \"question\" --dir <folder>` first "
        "(or export RESEARCH_OS_PROJECT=<project path>)")


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
