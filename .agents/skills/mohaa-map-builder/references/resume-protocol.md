# Resume and checkpoint protocol

## Startup

1. Run `git rev-parse --show-toplevel` and work from that root.
2. Read every applicable `AGENTS.md`.
3. Inspect `git status --porcelain=v2 --branch`, current branch, `git remote -v`,
   configured upstream, HEAD, and recent log.
4. Verify `origin` names `pstngh/moh-maps` using HTTPS or equivalent SSH form.
   If missing, configure the canonical URL. If it names another repository,
   stop and ask the user.
5. Fetch `origin`. Compare HEAD and upstream with ancestry, not timestamps.
6. Stop implementation if upstream is ahead or histories diverged. Never merge,
   rebase, reset, or force-push automatically. Inspect any local-ahead commits.
7. Inventory dirty paths and preserve them as user-owned unless the task clearly
   created them.
8. Read `PROJECT.md`, `PROJECT_STATE.json`, and run `validate_state.py`.
9. Read relevant decisions, rejections, gates, map README/revision reports, and
   only the references needed for the exact next action.
10. Compare checkpoint claims with Git, recent commits, files, and evidence. If
    they disagree, reconcile before map implementation and discard nothing.

Report the project goal/version, active map/revision, accepted baseline, latest
candidate, known defects, exact next action, stopping condition, dirty paths,
and local/upstream synchronization before continuing.

## State rules

- Treat `PROJECT_STATE.json` as the authoritative mutable checkpoint only while
  it agrees with repository evidence.
- Keep one authoritative `next_action`.
- Make the action executable by a new task with no chat history.
- Keep candidate and accepted baseline separate.
- Record approval only from explicit user approval of the tested revision.
- Preserve unknown state fields unless intentionally migrating the schema.
- Never put the containing commit hash into the committed state file.

## Checkpoint before stopping or risk

1. Save intentional source and evidence changes.
2. Update map status, current revision, defects, evidence, approval, and exact
   map-specific next action.
3. Update verified knowledge, decisions, and rejections.
4. Atomically set one top-level next action and stopping condition with
   `checkpoint.py`.
5. Run `validate_state.py` and all task-relevant validation.
6. Inspect Git status and the full diff.
7. Stage explicit intentional paths only; never use `git add .` or `git add -A`.
8. Inspect the staged diff and commit a coherent checkpoint.
9. Push the current branch to its configured upstream without force.
10. Fetch/resolve the upstream hash and require it to equal local HEAD.
11. Report the commit, upstream commit, push result, and remaining dirty paths.

If interrupted before commit, leave the diff intact for the next task. If push
fails, preserve the local commit and call the checkpoint incomplete.
