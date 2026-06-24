#!/usr/bin/env bash
#
# promptloop.sh — autonomous phase-execution loop (Ralph-style).
#
# Runs a FRESH `claude -p` per iteration against planning/PLAN.md: each tick reads
# the plan from disk, executes the next non-completed phase via the phase-executor
# skill in non-interactive LOOP MODE, and commits on success. Progress lives in git
# and PLAN.md, never in a growing conversation.
#
# RUN IT FROM YOUR SHELL (not from inside a Claude session):
#   bash .claude/scripts/promptloop.sh [MAX_ITERATIONS]
#   # log it:  bash .claude/scripts/promptloop.sh 8 2>&1 | tee "planning/loop-$(date +%F).log"
#
# SAFETY MODEL (permissions are skipped, so these compensating controls matter):
#   - Refuses to run on main/master — use a dedicated, disposable feature branch.
#   - Refuses to start with a dirty working tree.
#   - Commits once per completed phase → every step is revertible.
#   - The base's PreToolUse hooks STILL fire (rm -rf, force-push, git reset --hard,
#     --no-verify remain blocked) — --dangerously-skip-permissions does not bypass hooks.
#   - Hard stops: all phases COMPLETED · any BLOCKED task · MAX iterations · no progress.
#   - MAX iterations is the cost ceiling. Start small (e.g. 5) the first time.
#   Strongly recommended: run inside a container/sandbox or a throwaway branch.

set -uo pipefail

MAX="${1:-12}"
PLAN="planning/PLAN.md"

# ---- Pre-flight guards -------------------------------------------------------
command -v claude >/dev/null 2>&1 || { echo "✗ claude CLI not found on PATH"; exit 1; }
command -v git    >/dev/null 2>&1 || { echo "✗ git not found on PATH"; exit 1; }
[[ -f "$PLAN" ]] || { echo "✗ no $PLAN — run /plan-writing first"; exit 1; }

branch="$(git branch --show-current 2>/dev/null || true)"
if [[ -z "$branch" || "$branch" == "main" || "$branch" == "master" ]]; then
  echo "✗ refuse: run the loop on a dedicated feature branch, not '${branch:-<detached>}'"
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "✗ refuse: working tree has uncommitted changes — commit or stash first"
  exit 1
fi

# ---- Sequence gate: Loop 1 (planning) must be complete before Loop 2 (code) --
# The anchor must exist: PLAN.md needs Non-goals + Invariants + at least one Done-when.
grep -qE '^##[[:space:]]+Non-goals'  "$PLAN" || { echo "✗ refuse: $PLAN has no '## Non-goals' — finish the planning loop (/blueprint → /plan-writing) first"; exit 1; }
grep -qE '^##[[:space:]]+Invariants' "$PLAN" || { echo "✗ refuse: $PLAN has no '## Invariants' — finish the planning loop first"; exit 1; }
grep -qE '^[[:space:]]*Done when:'   "$PLAN" || { echo "✗ refuse: no phase has a 'Done when:' criterion — the plan is not loop-ready"; exit 1; }

# If a blueprint was started, it must be fully approved (no pending/in-progress/blocked docs).
MANIFEST="planning/blueprint/MANIFEST.md"
if [[ -f "$MANIFEST" ]] && grep -qE '^[[:space:]]*- \[( |>|!)\]' "$MANIFEST"; then
  echo "✗ refuse: blueprint is incomplete (unapproved or blocked docs in $MANIFEST) — finish /blueprint first"
  exit 1
fi

# ---- Helpers -----------------------------------------------------------------
next_phase() { grep -E '^### Phase ' "$PLAN" | grep -v '(COMPLETED)' | head -n1; }
has_blocked() { grep -qE '^[[:space:]]*- \[!\]' "$PLAN"; }
plan_sig()   { printf '%s|%s' "$(git rev-parse HEAD)" "$(md5sum "$PLAN" | awk '{print $1}')"; }

read -r -d '' LOOP_PROMPT <<'EOF'
Execute the next non-completed phase in planning/PLAN.md by following the
phase-executor skill in NON-INTERACTIVE LOOP MODE:
- Do NOT ask for approval; proceed autonomously on the first non-completed phase.
- Honor the plan's ## Non-goals and ## Invariants. If a task would violate either,
  mark it `- [!] ... (BLOCKED <date>: reason)` in PLAN.md and STOP without coding.
- Implement the phase's tasks, run the verification gate, and confirm the phase's
  `Done when:` criterion is met.
- On success: mark the phase title `(COMPLETED)` and create exactly ONE conventional commit.
- If anything is ambiguous, a dependency is missing, or verification fails: mark the
  affected task `- [!] ... (BLOCKED <date>: reason)` and STOP. Never guess. Never commit
  partial or unverified work.
EOF

# ---- The loop ----------------------------------------------------------------
echo "▶ promptloop on '$branch' — max $MAX iteration(s)"
i=0
while (( i < MAX )); do
  phase="$(next_phase)"
  if [[ -z "$phase" ]]; then echo "✓ all phases COMPLETED — done"; break; fi
  if has_blocked; then echo "■ a task is BLOCKED — stopping for human review"; break; fi

  echo "── iteration $((i+1))/$MAX → ${phase}"
  before="$(plan_sig)"

  if ! claude -p --dangerously-skip-permissions "$LOOP_PROMPT"; then
    echo "■ claude exited non-zero — stopping"; break
  fi

  if has_blocked; then echo "■ phase hit a BLOCKED task this iteration — stopping"; break; fi
  if [[ "$before" == "$(plan_sig)" ]]; then
    echo "■ no progress (PLAN.md and HEAD unchanged) — stopping to avoid a spin loop"; break
  fi
  i=$((i+1))
done

echo "▣ finished after $i iteration(s) on '$branch'. Review with: git log --oneline"
