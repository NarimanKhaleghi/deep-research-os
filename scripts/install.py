#!/usr/bin/env python3
"""install.py — install deep-research-os as an agent skill.

Targets: claude · opencode · codex · cursor · agents · all · generic (--dir).
Copy by default; --link symlinks instead (best for dev). --deps creates a
local .venv via uv (fallback: python -m venv) and installs requirements.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
REPO = _HERE.parent.parent  # repo root (this file lives in scripts/)
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

SKILL_NAME = "deep-research-os"

PLATFORMS: dict[str, list[Path]] = {
    "claude": [Path.home() / ".claude" / "skills" / SKILL_NAME],
    "opencode": [Path.home() / ".config" / "opencode" / "skills" / SKILL_NAME],
    "codex": [Path.home() / ".codex" / "skills" / SKILL_NAME],
    "cursor": [Path.home() / ".cursor" / "skills" / SKILL_NAME],
    "agents": [Path.home() / ".agents" / "skills" / SKILL_NAME],
}

IGNORE = shutil.ignore_patterns(
    ".git", ".venv", "venv", "__pycache__", "*.pyc", ".pytest_cache",
    "research-os", "exports", ".DS_Store", "*.egg-info",
)


def install_one(dest: Path, link: bool, force: bool, dry: bool) -> dict:
    dest = dest.expanduser()
    action = "copied"
    if dest.is_symlink():
        if dest.resolve() == REPO.resolve():
            return {"dest": str(dest), "action": "up-to-date (symlink)", "ok": True}
        if not force:
            return {"dest": str(dest), "action": "refused: existing symlink elsewhere (use --force)",
                    "ok": False}
        if not dry:
            dest.unlink()
    elif dest.exists():
        if not force:
            return {"dest": str(dest), "action": "refused: exists (use --force)", "ok": False}
        if not dry:
            shutil.rmtree(dest)

    if dry:
        return {"dest": str(dest), "action": f"would {'symlink' if link else 'copy'}", "ok": True}

    dest.parent.mkdir(parents=True, exist_ok=True)
    if link:
        dest.symlink_to(REPO, target_is_directory=True)
        action = "symlinked"
    else:
        shutil.copytree(REPO, dest, ignore=IGNORE)
        action = "copied"
    return {"dest": str(dest), "action": action, "ok": True}


def ensure_deps(dry: bool, base: Path | None = None) -> dict:
    base = (base or REPO).expanduser()
    venv = base / ".venv"
    req = REPO / "requirements.txt"
    if dry:
        return {"venv": str(venv), "action": "would create + install", "ok": True}
    if not venv.exists():
        uv = shutil.which("uv")
        try:
            if uv:
                subprocess.run([uv, "venv", str(venv)], check=True, capture_output=True)
            else:
                subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            return {"venv": str(venv), "action": f"venv creation failed: {exc}", "ok": False}
    py = venv / "bin" / "python"
    if not py.exists():
        py = venv / "Scripts" / "python.exe"  # windows
    uv = shutil.which("uv")
    if uv:
        pip_cmd = [uv, "pip", "install", "--python", str(py), "-r", str(req)]
    else:
        pip_cmd = [str(py), "-m", "pip", "install", "-r", str(req)]
    try:
        p = subprocess.run([c for c in pip_cmd if c], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        return {"venv": str(venv), "action": f"dependency install failed: {exc.stderr[-300:]}", "ok": False}
    return {"venv": str(venv), "action": "dependencies installed", "ok": True,
            "python": str(py)}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="install", description="install deep-research-os as a skill")
    ap.add_argument("--platform", default="all",
                    choices=["claude", "opencode", "codex", "cursor", "agents", "all", "generic"])
    ap.add_argument("--dir", help="destination for --platform generic")
    ap.add_argument("--link", action="store_true", help="symlink instead of copy")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--deps", action="store_true", help="create .venv and install requirements")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    dry = args.dry_run
    results: list[dict] = []

    if args.platform == "generic":
        if not args.dir:
            print(json.dumps({"error": "--platform generic requires --dir PATH"}, indent=2))
            sys.exit(2)
        results.append(install_one(Path(args.dir), args.link, args.force, dry))
    else:
        names = sorted(PLATFORMS) if args.platform == "all" else [args.platform]
        for name in names:
            for dest in PLATFORMS[name]:
                r = install_one(dest, args.link, args.force, dry)
                r["platform"] = name
                results.append(r)

    deps: list[dict] | None = None
    if args.deps:
        deps = []
        if args.link:
            deps.append(ensure_deps(dry, REPO))
        else:
            seen_dests: set[str] = set()
            for r in results:
                if r.get("ok"):
                    d = str(Path(r["dest"]))
                    if d not in seen_dests:
                        seen_dests.add(d)
                        deps.append(ensure_deps(dry, Path(r["dest"])))
    ok = all(r["ok"] for r in results) and (deps is None or all(d["ok"] for d in deps))

    payload = {
        "ok": ok,
        "repo": str(REPO),
        "installs": results,
        "deps": deps,
        "next": [
            f"python3 {REPO}/scripts/research_ctl.py doctor",
            f'python3 {REPO}/scripts/research_ctl.py init "your question" --profile standard',
        ],
        "notes": [
            "skill entry point: SKILL.md (agent loads it automatically once installed)",
            "runtime data: ~/.config/deep-research-os (override RESEARCH_OS_HOME)",
            "vault: ./research-os in the working directory (override RESEARCH_OS_VAULT)",
        ],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
