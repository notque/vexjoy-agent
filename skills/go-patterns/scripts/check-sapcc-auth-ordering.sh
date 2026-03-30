#!/usr/bin/env bash
set -euo pipefail

# Checks that authentication happens before data access in HTTP handlers.
# Rule: sapcc handler pattern requires auth check before any db/resource load.

VERSION="1.0.0"
SCRIPT_NAME="$(basename "$0")"

usage() {
    cat <<EOF
$SCRIPT_NAME v$VERSION — Check sapcc HTTP handlers for data access before authentication

USAGE
    bash $SCRIPT_NAME [options] [path]

DESCRIPTION
    Scans Go source files in internal/api/ directories for HTTP handlers
    that access data (db.Get, db.Select, findAccount, etc.) before calling
    authenticateRequest or similar auth functions.

    Exits 0 if auth ordering is correct, 1 if violations found, 2 on error.

OPTIONS
    -h, --help       Show this help message
    -v, --version    Show version
    --json           Output results as JSON
    --limit N        Show at most N results (default: all)

ARGUMENTS
    path             Directory to scan (default: current directory)

EXAMPLES
    bash $SCRIPT_NAME ./internal/api
    bash $SCRIPT_NAME --json .
EOF
}

JSON_OUTPUT=false
LIMIT=0
TARGET=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)    usage; exit 0 ;;
        -v|--version) echo "$SCRIPT_NAME v$VERSION"; exit 0 ;;
        --json)       JSON_OUTPUT=true; shift ;;
        --limit)      LIMIT="${2:?error: --limit requires a number}"; shift 2 ;;
        -*)           echo "error: unknown option: $1" >&2; usage >&2; exit 2 ;;
        *)            TARGET="$1"; shift ;;
    esac
done

TARGET="${TARGET:-.}"

if ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
    echo "error: --limit must be a non-negative integer, got: $LIMIT" >&2
    exit 2
fi

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\t'/\\t}"
    s="${s//$'\r'/}"
    s="${s//$'\n'/\\n}"
    printf '%s' "$s"
}

FINDINGS=()

# Auth patterns (must appear before data access)
AUTH_PATTERNS='authenticate|authorize|authz|gopherpolicy\.Token'
# Data access patterns (must appear after auth)
DATA_PATTERNS='\.Get\(|\.Select\(|\.Find\(|\.findAccount|\.findRepo|db\.Get|db\.Select|db\.Query'

check_file() {
    local file="$1"
    local in_handler=false
    local handler_line=0
    local handler_name=""
    local found_auth=false
    local line_num=0

    while IFS= read -r line; do
        line_num=$((line_num + 1))

        # Detect handler function
        if [[ "$line" =~ func[[:space:]] ]] && \
           [[ "$line" =~ http\.ResponseWriter ]] && [[ "$line" =~ \*http\.Request ]]; then
            in_handler=true
            handler_line=$line_num
            handler_name=$(echo "$line" | grep -oE 'func[[:space:]]+(\([^)]+\)[[:space:]]+)?[a-zA-Z_][a-zA-Z0-9_]*' | head -1 | sed 's/func[[:space:]]*//' | sed 's/([^)]*)[[:space:]]*//')
            found_auth=false
        fi

        if $in_handler; then
            # Check for auth call
            if echo "$line" | grep -qE "$AUTH_PATTERNS"; then
                found_auth=true
            fi

            # Check for data access before auth
            if ! $found_auth && echo "$line" | grep -qE "$DATA_PATTERNS"; then
                # Skip comments
                local trimmed
                trimmed=$(echo "$line" | sed 's/^[[:space:]]*//')
                if [[ ! "$trimmed" =~ ^// ]]; then
                    FINDINGS+=("${file}:${line_num}|${handler_name}|data access before authentication")
                    in_handler=false  # Only report first violation per handler
                fi
            fi

            # End of function (simple heuristic: closing brace at column 0-1)
            if [[ "$line" =~ ^[[:space:]]?\}[[:space:]]*$ ]] && [[ $((line_num - handler_line)) -gt 2 ]]; then
                in_handler=false
            fi
        fi
    done < "$file"
}

FILES=()
while IFS= read -r f; do
    [[ -n "$f" ]] && FILES+=("$f")
done < <(find "$TARGET" -name '*.go' ! -name '*_test.go' ! -path '*/vendor/*' ! -path '*/.git/*' 2>/dev/null)

if [[ ${#FILES[@]} -eq 0 ]]; then
    if $JSON_OUTPUT; then
        echo '{"findings":[],"total":0,"truncated":false,"status":"no_go_files"}'
    else
        echo "No Go files found in: $TARGET"
    fi
    exit 0
fi

for file in "${FILES[@]}"; do
    if grep -q 'http\.ResponseWriter' "$file" 2>/dev/null; then
        check_file "$file"
    fi
done

TOTAL=${#FINDINGS[@]}
TRUNCATED=false
if [[ $LIMIT -gt 0 && $TOTAL -gt $LIMIT ]]; then
    FINDINGS=("${FINDINGS[@]:0:$LIMIT}")
    TRUNCATED=true
fi

if $JSON_OUTPUT; then
    echo "{"
    echo '  "findings": ['
    first=true
    for entry in "${FINDINGS[@]+"${FINDINGS[@]}"}"; do
        IFS='|' read -r location name message <<< "$entry"
        file="${location%%:*}"
        line="${location#*:}"
        $first || echo ","
        first=false
        printf '    {"file":"%s","line":%s,"handler":"%s","message":"%s"}' \
            "$(json_escape "$file")" "$line" "$(json_escape "$name")" "$(json_escape "$message")"
    done
    echo ""
    echo "  ],"
    printf '  "total": %d,\n' "$TOTAL"
    printf '  "truncated": %s\n' "$TRUNCATED"
    echo "}"
else
    if [[ $TOTAL -eq 0 ]]; then
        echo "All handlers authenticate before data access."
        exit 0
    fi
    echo "Handlers with data access before authentication:"
    echo ""
    for entry in "${FINDINGS[@]}"; do
        IFS='|' read -r location name message <<< "$entry"
        printf "  %s  handler '%s': %s\n" "$location" "$name" "$message"
    done
    if $TRUNCATED; then
        echo "  ... and $((TOTAL - LIMIT)) more"
    fi
    echo ""
    echo "Total: $TOTAL violation(s)"
fi

[[ $TOTAL -gt 0 ]] && exit 1
exit 0
