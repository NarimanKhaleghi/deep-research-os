# Scheduler Recipes — running the slow loop

The learning engine's slow loop (maintenance, upstream scans, digests) is designed
to run *periodically* independent of research runs. Any scheduler works; these are
copy-paste recipes for common environments. All commands are idempotent and write
JSON results you can log.

## What to schedule

| Job | Command | Cadence | Why |
| --- | --- | --- | --- |
| Maintenance | `research_ctl.py learn maintain` | monthly (or every 10 runs) | Stats recompute, proposals generated |
| Upstream scan | `research_ctl.py learn scan-upstream` | monthly (offset from maintain by ~2 weeks) | Discover new tools/methods |
| Digest | `research_ctl.py learn digest` | monthly | Human-readable `digest-YYYY-MM.md` |
| Integrity re-check | `research_ctl.py verify --online --all-projects` | quarterly | Retraction lag sweep |

The skill also checks "maintenance due" at every intake (phase 0) and mentions it
once if overdue — scheduling is belt-and-braces, not a hard requirement.

## cron (Linux/macOS)

```cron
# m h dom mon dow  command
0 9 1 * *    /path/to/venv/bin/python /path/to/deep-research-os/scripts/research_ctl.py learn maintain   >> ~/.config/deep-research-os/cron.log 2>&1
0 9 15 * *   /path/to/venv/bin/python /path/to/deep-research-os/scripts/research_ctl.py learn scan-upstream >> ~/.config/deep-research-os/cron.log 2>&1
0 9 2 * *    /path/to/venv/bin/python /path/to/deep-research-os/scripts/research_ctl.py learn digest     >> ~/.config/deep-research-os/cron.log 2>&1
```

## systemd user timer

`~/.config/systemd/user/research-os-maintain.service`:

```ini
[Unit]
Description=deep-research-os monthly maintenance
[Service]
Type=oneshot
ExecStart=/path/to/venv/bin/python /path/to/deep-research-os/scripts/research_ctl.py learn maintain
```

`research-os-maintain.timer`:

```ini
[Unit]
Description=Monthly research-os maintenance
[Timer]
OnCalendar=monthly
Persistent=true
[Install]
WantedBy=timers.target
```

Then: `systemctl --user daemon-reload && systemctl --user enable --now research-os-maintain.timer`.
Repeat for `scan-upstream` with `OnCalendar=monthly` shifted, or a second timer.

## GitHub Actions (repo health, no research data)

For **upstream scanning of this repo's watchlist** (safe for CI; operates on the
repo's own `learnings/`):

```yaml
name: upstream-scan
on:
  schedule: [{cron: "0 9 15 * *"}]
  workflow_dispatch:
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install -r requirements.txt
      - run: python scripts/research_ctl.py learn scan-upstream --repo-mode
      - uses: actions/upload-artifact@v4
        with: {name: discoveries, path: learnings/discoveries/}
```

`--repo-mode` writes discoveries into the repo (not `~/.config/…`) and never
touches personal feedback/stat files — used by maintainers to prune the watchlist.

## Outputs to check after any scheduled run

1. `learn status` — pending proposals count (these wait for *you*; they never apply
   themselves).
2. `learnings/digest-YYYY-MM.md` — the monthly story.
3. `learnings/discoveries/YYYY-MM.md` — new-tool candidates with recommendations.

Scheduled jobs never run phase work, never touch research vaults, and never apply
proposals — that boundary is by design (`learning-protocol.md` §2, §7).
