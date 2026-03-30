#!/usr/bin/env bash
set -euo pipefail

# Checks that every HTTP handler calls httpapi.IdentifyEndpoint as its first operation.
# Rule: sapcc handler pattern requires endpoint identification for metrics.

VERSION="1.0.0"
SCRIPT_NAME="$(basename "$0")"

usage() {
    cat <<EOF
$SCRIPT_NAME v$VERSION — Check sapcc HTTP handlers for missing httpapi.IdentifyEndpoint

USAGE
    bash $SCRIPT_NAME [options] [path]

DESCRIPTION
    Scans Go source files for HTTP handler functions (accepting
    http.ResponseWriter and *http.Request) and checks that
    httpapi.IdentifyEndpoint is called within the first 5 lines
    of the function body.

    Exits 0 if all handlers are compliant, 1 if violations found, 2 on error.

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

# Scan a file for handler functions missing IdentifyEndpoint
check_file() {
    local file="$1"
    local in_handler=false
    local handler_line=0
    local handler_name=""
    local lines_into_body=0
    local found_identify=false
    local brace_depth=0
    local line_num=0

    while IFS= read -r line; do
        line_num=$((line_num + 1))

        # Detect handler function signature: func ... (w http.ResponseWriter, r *http.Request)
        if [[ "$line" =~ func[[:space:]]+\(?[^)]*\)?[[:space:]]*[a-zA-Z_][a-zA-Z0-9_]*\( ]] && \
           [[ "$line" =~ http\.ResponseWriter ]] && [[ "$line" =~ \*http\.Request ]]; then
            in_handler=true
            handler_line=$line_num
            handler_name=$(echo "$line" | grep -oE 'func[[:space:]]+(\([^)]+\)[[:space:]]+)?[a-zA-Z_][a-zA-Z0-9_]*' | head -1 | sed 's/func[[:space:]]*//' | sed 's/([^)]*)[[:space:]]*//')
            lines_into_body=0
            found_identify=false
            brace_depth=0
        fi

        if $in_handler; then
            # Count opening braces to track we're in the function body
            local opens="${line//[^\{]/}"
            local closes="${line//[^\}]/}"
            brace_depth=$((brace_depth + ${#opens} - ${#closes}))
            lines_into_body=$((lines_into_body + 1))

            # Check for IdentifyEndpoint call
            if [[ "$line" =~ httpapi\.IdentifyEndpoint ]] || [[ "$line" =~ IdentifyEndpoint ]]; then
                found_identify=true
            fi

            # After 8 lines into the handler, check if we found it
            if [[ $lines_into_body -ge 8 ]] || [[ $brace_depth -le 0 && $lines_into_body -gt 1 ]]; then
                if ! $found_identify; then
                    FINDINGS+=("${file}:${handler_line}|${handler_name}|missing httpapi.IdentifyEndpoint call in handler")
                fi
                in_handler=false
            fi
        fi
    done < "$file"

    # Handle case where handler is at end of file
    if $in_handler && ! $found_identify; then
        FINDINGS+=("${file}:${handler_line}|${handler_name}|missing httpapi.IdentifyEndpoint call in handler")
    fi
}

# Find Go files (exclude tests and vendor)
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
    # Only check files that import httpapi or have handler-like signatures
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
        echo "All HTTP handlers call httpapi.IdentifyEndpoint."
        exit 0
    fi
    echo "Handlers missing httpapi.IdentifyEndpoint:"
    echo ""
    for entry in "${FINDINGS[@]}"; do
        IFS='|' read -r location name message <<< "$entry"
        printf "  %s  handler '%s': %s\n" "$location" "$name" "$message"
    done
    if $TRUNCATED; then
        echo "  ... and $((TOTAL - LIMIT)) more"
    fi
    echo ""
    echo "Total: $TOTAL handler(s) missing IdentifyEndpoint"
fi

[[ $TOTAL -gt 0 ]] && exit 1
exit 0
