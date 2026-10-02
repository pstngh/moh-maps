#!/bin/bash
# Stop hook (CLAUDE.md "The learning loop"): when a turn hands the session off (the one-line
# handoff "Read CLAUDE.md and HANDOFF.md, then continue"), block the stop once so the agent
# harvests the session's lessons into code, docs, docs/symptoms.md or memory first.
# stop_hook_active is true on the follow-up stop, so it never loops.
input=$(cat)
[ "$(printf '%s' "$input" | jq -r '.stop_hook_active // false')" = "true" ] && exit 0
msg=$(printf '%s' "$input" | jq -r '.last_assistant_message // empty')
if [ -z "$msg" ]; then
  tp=$(printf '%s' "$input" | jq -r '.transcript_path // empty')
  if [ -n "$tp" ] && [ -f "$tp" ]; then
    msg=$(tail -n 400 "$tp" | jq -rs '[.[] | select(.type == "assistant") | .message.content[]?
          | select(.type == "text") | .text] | last // empty' 2>/dev/null)
  fi
fi
case "$msg" in
  *"Read CLAUDE.md and HANDOFF.md"*)
    jq -n '{decision: "block", reason: "Session handoff detected. Before stopping, do the harvest from CLAUDE.md \"The learning loop\": move every durable lesson of this session (calibrations, techniques, engine or tool facts, approaches tried and rejected with numbers, looks that were wrong and their fixes, user preferences) out of HANDOFF.md and the chat into code (defaults, checks, tests), the topic docs, docs/symptoms.md or memory; then commit and push. If that is already done, say so in one line and stop."}'
    ;;
esac
exit 0
