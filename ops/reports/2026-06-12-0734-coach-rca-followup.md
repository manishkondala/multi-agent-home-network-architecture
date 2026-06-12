# coach: RCA follow-up — agent instruction updates (2026-06-12 07:34)

**Trigger:** owner directive after `ops/reports/2026-06-12-0730-rca-dev-token-burn.md`
(dev: 375 turns / ~170k context on the app-porting task).

## Changes

### .claude/agents/dev.md
- Fixed stale instruction in Platform contract #1: "rsync the build context over" →
  git-snapshot-over-ssh (`scripts/sync-apps.sh` pattern); rsync is deny-listed on the Mac
  and this line seeded the 16-denial thrash.
- Added `## Working efficiently (RCA 2026-06-12)`:
  1. Slow remote commands (Pi build ≈ 10 min) = ONE Bash call with `timeout: 600000` or
     detach via `nohup ... > ~/build-<name>.log 2>&1 &` and check the log once. No
     poll-spin (no `sleep N` turns, no `until ssh ...; do sleep; done` variants).
  2. Unique image tag per build (git short SHA / timestamp) so "image exists" ≠ stale tag;
     or watch the build log.
  3. 2-denial rule: two denials of the same operation class → switch to an allowed pattern
     or end the run reporting the blocker.
  4. Read before Edit/Write to existing files (7 wasted error round-trips in the incident).
  5. Run-size budget: >~100 tool calls → do the top slice, end with done/remaining report.
- Added `## Mac command patterns`: denied = ad-hoc rsync/scp, tar -czf, curl to arbitrary
  hosts, `security add-generic-password` w/ command substitution, chmod,
  cd-in-compound-commands; allowed = `ssh pi-node1 "..."`, git (incl. `git archive | ssh`),
  `ssh pi-node1 "cat > remote" < local`.

### .claude/agents/infra.md
- Added `## Working efficiently (shared rules — RCA 2026-06-12)`: no-poll-spin /
  single-long-timeout-or-detach rule; unique tag per image build (infra builds/pulls
  images); 2-denial rule plus the full denied/allowed command list (incl. `scripts/deploy.sh`
  as the allowed deploy path); Read-before-Edit.

### .claude/agents/netops.md
- Added shared section: long-timeout-or-detach for slow probes/scans; no poll-spin;
  2-denial rule; Read-before-Edit. No image-tagging rule (netops builds no images).

### .claude/agents/watchdog.md
- Added shared section, adapted to a read-only agent: no poll-spin — "needs time to settle"
  is a finding, not a reason to wait in-run; 2-denial rule with fallback = report the check
  as NOT RUN naming the blocker; Read-before-Write to existing files.

### docs/LEARNINGS.md
- One new bullet under the existing RCA section (not duplicating RCA lessons): the denial
  thrash was partly self-inflicted because dev.md itself recommended rsync; rule — when a
  deny rule is added, grep `.claude/agents/*.md` for instructions recommending the
  now-denied command the same session.

## Not done (per constraints)
- CLAUDE.md, deploy/, the Pi: untouched. Suggestion for the CTO (approval needed): the
  denied/allowed command list could also live in CLAUDE.md so the main session and any
  future agent inherit it; today it is in dev.md + infra.md only.
