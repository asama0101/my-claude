#!/bin/bash
# Skill / MCP tool 使用をセッションログに追記する PostToolUse フック
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
SKILL=$(echo "$INPUT" | jq -r '.tool_input.skill // empty')
QUERY=$(echo "$INPUT" | jq -r '.tool_input.query // empty')
LIB=$(echo "$INPUT" | jq -r '.tool_input.library_id // empty')

LOG_FILE="/home/asama/.claude/logs/session-usage-$(date '+%Y%m%d').log"
mkdir -p "$(dirname "$LOG_FILE")"
TIMESTAMP=$(date '+%H:%M:%S')

case "$TOOL" in
  Skill)
    echo "[$TIMESTAMP] Skill: $SKILL" >> "$LOG_FILE"
    ;;
  Agent)
    AGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // "general-purpose"')
    DESCRIPTION=$(echo "$INPUT" | jq -r '.tool_input.description // empty')
    echo "[$TIMESTAMP] Agent(${AGENT_TYPE}): ${DESCRIPTION}" >> "$LOG_FILE"
    ;;
  mcp__plugin_context7_context7__query-docs)
    echo "[$TIMESTAMP] context7 query-docs: lib=${LIB} query=${QUERY:0:50}" >> "$LOG_FILE"
    ;;
  mcp__plugin_context7_context7__resolve-library-id)
    echo "[$TIMESTAMP] context7 resolve: ${QUERY:0:50}" >> "$LOG_FILE"
    ;;
esac

exit 0
