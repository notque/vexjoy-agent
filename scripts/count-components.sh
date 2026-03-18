#!/bin/bash
#
# Count components in the agents repository
# Usage: ./scripts/count-components.sh [--json]
#
# Outputs counts for agents, skills, commands, and hooks.
# Used by install.sh and can be used to update documentation.
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Count each component type
AGENT_COUNT=$(ls -1 "${SCRIPT_DIR}/agents/"*.md 2>/dev/null | grep -v README | wc -l)
SKILL_COUNT=$(ls -1d "${SCRIPT_DIR}/skills/"*/ 2>/dev/null | wc -l)
COMMAND_COUNT=$(find "${SCRIPT_DIR}/commands" -name "*.md" -not -name "README.md" 2>/dev/null | wc -l)
HOOK_COUNT=$(ls -1 "${SCRIPT_DIR}/hooks/"*.py 2>/dev/null | wc -l)

if [ "$1" = "--json" ]; then
    cat << EOF
{
  "agents": ${AGENT_COUNT},
  "skills": ${SKILL_COUNT},
  "commands": ${COMMAND_COUNT},
  "hooks": ${HOOK_COUNT},
  "generated": "$(date -Iseconds)"
}
EOF
else
    echo "Component counts:"
    echo "  Agents:   ${AGENT_COUNT}"
    echo "  Skills:   ${SKILL_COUNT}"
    echo "  Commands: ${COMMAND_COUNT}"
    echo "  Hooks:    ${HOOK_COUNT}"
fi
