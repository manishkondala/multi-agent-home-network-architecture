# RCA: dev agent token burn (~170k context, 375 turns) — 2026-06-12

**Author:** CTO session. **Severity:** cost/efficiency incident — no production impact, no data loss.
**Evidence:** subagent transcript `agent-ae2a43829395bc695.jsonl` (session `7353be05`), task
"Port apps + homepage redesign".

## Summary
The dev agent was not in an infinite loop and had not lost the plot — it was interrupted at
07:16 while writing its *completion report* (the apps were built, deployed, and probed green).
But it got there grotesquely inefficiently: **375 assistant turns, 214 tool calls (124 Bash),
94k output tokens, 740k cache-write tokens, and 40.3M cache-read tokens**, because each of the
375 turns re-reads the entire accumulated context (~110k average, ~170k by the end).

The burn had four compounding causes; the dominant one was a **poll-spin** while waiting for a
~10-minute `next build` on the Pi 4.

## Timeline (EDT)
- **22:36–22:47 (Jun 11):** recon + first transfer attempts. 10 permission denials in a row as
  it tried `rsync` (×5), `scp`, `tar`, `curl`, `security`, `chmod` — all blocked by local deny
  rules/sandbox. It pivoted to the git-snapshot-over-ssh transfer (commit `31f3e0e`).
- **(gap — Mac asleep / session paused)**
- **06:53–07:04 (Jun 12):** resumed; synced both apps, built stock-backend/frontend, started the
  cc-points image build on the Pi (Next.js on a Pi 4 ≈ 10 min per build, and the Dockerfile
  needed two fixes → **three builds total**).
- **07:04–07:15:** the poll-spin. ~60% of all turns happened in these 11 minutes.
- **07:16:** agent said "Everything checks out. Ticking the roadmap, writing the completion
  report, and final commit" — and was interrupted by the owner.

## Root causes

### 1. Poll-spin on a slow remote build (primary)
Instead of running the Pi-side `docker build` as a single long-timeout call (Bash allows 600s)
or detaching it on the Pi (`nohup docker build > build.log` and checking the log), the agent
ran the build with `tail` in one call, then spent 11 minutes issuing **~15 different wait
constructs**: a blocked `sleep 300`, then `until ssh pi-node1 "docker image inspect …"; do
sleep 30/45/60/90; done` in at least 6 variants, interleaved with `date`, `ps`, `vcgencmd`,
`docker images`, and probe re-checks.

### 2. The wait condition was wrong, so every wait "succeeded" instantly
`docker image inspect cc-points:0.1.0` returned true immediately because the **old** image with
the same tag already existed from the previous build. Each until-loop exited at once, the agent
saw the stale image, realized the check proved nothing, and invented a new condition (grep the
image `Created` timestamp, container `StartedAt` regex, `docker logs … 'Ready in'`, curl 200) —
several of which had timezone/regex bugs of their own. A unique tag per build (or checking the
build process/log, not the tag) would have made one check sufficient.

### 3. Permission-denial thrash (16 denials)
The sandbox/deny rules blocked `rsync`, `scp`, `tar -czf`, `curl` to Docker Hub, `security
add-generic-password`, and `chmod`. The agent burned ~20 turns rediscovering the same wall from
different angles before changing strategy. It never paused to report "I'm blocked on file
transfer, here's my plan B" — subagents can't ask, but they *can* fail fast to a documented
fallback instead of brute-forcing variants.

### 4. Oversized single task
One spawn was asked to do: port two apps (3 images), write 4 Dockerfiles + compose services,
add blackbox-exporter + Prometheus jobs, build a Grafana dashboard, redesign Homepage, manage
secrets, and document everything. Even executed perfectly that's a 150+ tool-call task, which
guarantees a six-figure context by the end — every later turn pays cache-read on all earlier
output. The work should have been 2–3 sequential spawns (sync+build / monitoring / homepage),
each starting with a fresh, small context.

### Aggravating factor: 7 `File has not been read yet` Edit/Write errors
Pure waste — the agent edited files it hadn't Read. Each error is a full round-trip at full
context price.

## What went right
- It never touched the forbidden things: no local Docker, pihole untouched, legacy jsms
  containers left stopped, no secrets committed.
- The work itself is done and was verified (probes green, apps responding 200).

## Corrective actions
1. **coach** updates `.claude/agents/dev.md` (and the shared patterns in infra/netops where
   relevant) with: long-running remote command protocol, no-poll-spin rule, unique image tags
   per build, 3-strikes rule on permission denials, task-size budget with progress checkpoints,
   and Read-before-Edit discipline. *(Owner directive, 2026-06-12.)*
2. **CTO** (me): stop issuing mega-tasks to a single spawn; split owner directives into
   sequential subagent runs with explicit scope and a tool-call budget in the prompt.
3. `docs/LEARNINGS.md` updated with the poll-spin and stale-tag lessons.
