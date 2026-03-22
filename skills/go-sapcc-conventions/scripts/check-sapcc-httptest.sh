#!/usr/bin/env bash
set -euo pipefail

# Checks for direct httptest.NewRecorder usage instead of assert.HTTPRequest.
# Rule: sapcc uses go-bits/assert.HTTPRequest for HTTP testing.

VERSION="1.0.0"
SCRIPT_NAME="$(basename "$0")"

usage() {
    cat <<EOF
$SCRIPT_NAME v$VERSION — Check for httptest.NewRecorder instead of assert.HTTPRequest

USAGE
    bash $SCRIPT_NAME [options] [path]

DESCRIPTION
    Scans Go test files for direct use of httptest.NewRecorder().
    sapcc convention uses go-bits/assert.HTTPRequest{}.Check(t, h)
    instead of manual recorder setup.

    Exits 0 if no violations found, 1 if violations found, 2 on error.

OPTIONS
    -h, --help       Show this help message
    -v, --version    Show version
    --json           Output results as JSON
    --limit N        Show at most N results (default: all)

ARGUMENTS
    path             Directory to scan (default: current directory)

EXAMPLES
    bash $SCRIPT_NAME ./internal
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

# Only scan test files
FILES=()
while IFS= read -r f; do
    [[ -n "$f" ]] && FILES+=("$f")
done < <(find "$TARGET" -name '*_test.go' ! -path '*/vendor/*' ! -path '*/.git/*' 2>/dev/null)

if [[ ${#FILES[@]} -eq 0 ]]; then
    if $JSON_OUTPUT; then
        echo '{"findings":[],"total":0,"truncated":false,"status":"no_test_files"}'
    else
        echo "No Go test files found in: $TARGET"
    fi
    exit 0
fi

for file in "${FILES[@]}"; do
    if ! grep -q 'httptest\.NewRecorder' "$file" 2>/dev/null; then
        continue
    fi
    line_num=0
    while IFS= read -r line; do
        line_num=$((line_num + 1))
        if [[ "$line" =~ httptest\.NewRecorder ]]; then
            FINDINGS+=("${file}:${line_num}|use assert.HTTPRequest{}.Check(t, h) instead of httptest.NewRecorder()")
        fi
    done < "$file"
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
        IFS='|' read -r location message <<< "$entry"
        file="${location%%:*}"
        line="${location#*:}"
        $first || echo ","
        first=false
        printf '    {"file":"%s","line":%s,"message":"%s"}' \
            "$(json_escape "$file")" "$line" "$(json_escape "$message")"
    done
    echo ""
    echo "  ],"
    printf '  "total": %d,\n' "$TOTAL"
    printf '  "truncated": %s\n' "$TRUNCATED"
    echo "}"
else
    if [[ $TOTAL -eq 0 ]]; then
        echo "No direct httptest.NewRecorder usage found."
        exit 0
    fi
    echo "Direct httptest.NewRecorder usage (use assert.HTTPRequest instead):"
    echo ""
    for entry in "${FINDINGS[@]}"; do
        IFS='|' read -r location message <<< "$entry"
        printf "  %s  %s\n" "$location" "$message"
    done
    if $TRUNCATED; then
        echo "  ... and $((TOTAL - LIMIT)) more"
    fi
    echo ""
    echo "Total: $TOTAL finding(s)"
fi

[[ $TOTAL -gt 0 ]] && exit 1
exit 0
