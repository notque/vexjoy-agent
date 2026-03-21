#!/usr/bin/env bash
set -euo pipefail

# Adapted from cxuu/golang-skills (Apache-2.0)
# Modified: removed string-error-compare check (covered by golangci-lint errorlint)

VERSION="1.0.0"
SCRIPT_NAME="$(basename "$0")"

usage() {
    cat <<EOF
$SCRIPT_NAME v$VERSION — Check Go code for error handling anti-patterns

USAGE
    bash $SCRIPT_NAME [options] [path]

DESCRIPTION
    Scans Go source files for error handling anti-patterns:
      - Bare 'return err' without wrapping context
      - Errors that are both logged and returned (handle once)

    Note: err.Error() string comparison is NOT checked here — it is
    already covered by golangci-lint's errorlint linter.

    Exits 0 if no issues found, 1 if anti-patterns detected, 2 on error.

OPTIONS
    -h, --help       Show this help message
    -v, --version    Show version
    --json           Output results as JSON
    --no-bare-return Skip the bare 'return err' check (high false-positive rate)
    --limit N        Show at most N results (default: all)

ARGUMENTS
    path             Directory or file to check (default: current directory)

EXAMPLES
    bash $SCRIPT_NAME
    bash $SCRIPT_NAME ./pkg/api
    bash $SCRIPT_NAME --json .
    bash $SCRIPT_NAME --no-bare-return ./internal
EOF
}

JSON_OUTPUT=false
CHECK_BARE_RETURN=true
LIMIT=0
TARGET=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)         usage; exit 0 ;;
        -v|--version)      echo "$SCRIPT_NAME v$VERSION"; exit 0 ;;
        --json)            JSON_OUTPUT=true; shift ;;
        --no-bare-return)  CHECK_BARE_RETURN=false; shift ;;
        --limit)           LIMIT="${2:?error: --limit requires a number}"; shift 2 ;;
        -*)                echo "error: unknown option: $1" >&2; usage >&2; exit 2 ;;
        *)                 TARGET="$1"; shift ;;
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

find_go_files() {
    local t="$1"
    if [[ -f "$t" ]]; then
        echo "$t"
    elif [[ -d "$t" ]]; then
        find "$t" -name '*.go' ! -name '*_test.go' ! -path '*/vendor/*' ! -path '*/.git/*' 2>/dev/null
    else
        local dir="${t%%/...}"
        dir="${dir:-.}"
        if [[ -d "$dir" ]]; then
            find "$dir" -name '*.go' ! -name '*_test.go' ! -path '*/vendor/*' ! -path '*/.git/*' 2>/dev/null
        else
            echo "error: path not found: $t" >&2
            exit 2
        fi
    fi
}

FINDINGS=()

add_finding() {
    local file="$1" line="$2" rule="$3" message="$4"
    FINDINGS+=("${file}:${line}|${rule}|${message}")
}

# Rule 1: Bare return err (no wrapping)
check_bare_return_err() {
    local file="$1"
    local line_num=0
    local in_error_block=false

    while IFS= read -r line; do
        line_num=$((line_num + 1))

        # Detect if err != nil { block
        pat='if[[:space:]]+(.*err[[:space:]]*(!=|==)[[:space:]]*nil|err[[:space:]]*:=)'
        if [[ "$line" =~ $pat ]]; then
            in_error_block=true
        fi

        # Check for bare "return err" that is not wrapped
        pat='^[[:space:]]*return[[:space:]]+(.*,)?[[:space:]]*err[[:space:]]*$'
        if $in_error_block && [[ "$line" =~ $pat ]]; then
            local trimmed
            trimmed=$(echo "$line" | sed 's/^[[:space:]]*//')
            if [[ "$trimmed" == "return err" ]]; then
                add_finding "$file" "$line_num" "bare-return-err" \
                    "bare 'return err' without wrapping context; consider fmt.Errorf('...: %w', err)"
            fi
        fi

        # Reset error block tracking on closing brace
        pat_close='^[[:space:]]*\}[[:space:]]*$'
        if $in_error_block && [[ "$line" =~ $pat_close ]]; then
            in_error_block=false
        fi
    done < "$file"
}

# Rule 2: Log-and-return (handle errors once)
check_log_and_return() {
    local file="$1"
    local line_num=0
    local prev_lines=()

    while IFS= read -r line; do
        line_num=$((line_num + 1))
        prev_lines+=("$line")

        # Keep a small window to detect log followed by return err
        if [[ ${#prev_lines[@]} -gt 5 ]]; then
            prev_lines=("${prev_lines[@]:1}")
        fi

        # Check if current line is 'return ... err' and a recent line logged the error
        pat='^[[:space:]]*return[[:space:]]+(.*,)?[[:space:]]*err'
        if [[ "$line" =~ $pat ]]; then
            local window_size=${#prev_lines[@]}
            for ((i=0; i<window_size-1; i++)); do
                local prev="${prev_lines[$i]}"
                # Match log.Print/Printf/Println/Error/Errorf/Warn/Warnf with err
                # Also match logg.Error (sapcc go-bits pattern)
                pat_log1='(log\.|logger\.|slog\.|logg\.)[a-zA-Z]*\(.*[^a-zA-Z]err[^a-zA-Z]'
                pat_log2='(log\.|logger\.|slog\.|logg\.)[a-zA-Z]*\(err[,\)]'
                if [[ "$prev" =~ $pat_log1 ]] || \
                   [[ "$prev" =~ $pat_log2 ]]; then
                    local log_line=$((line_num - window_size + 1 + i))
                    add_finding "$file" "$log_line" "log-and-return" \
                        "error is both logged (line $log_line) and returned (line $line_num); handle errors once"
                    break
                fi
            done
        fi
    done < "$file"
}

FILES=()
while IFS= read -r f; do
    [[ -n "$f" ]] && FILES+=("$f")
done < <(find_go_files "$TARGET")

if [[ ${#FILES[@]} -eq 0 ]]; then
    if $JSON_OUTPUT; then
        echo '{"findings":[],"total":0,"truncated":false,"status":"no_go_files"}'
    else
        echo "No Go files found in: $TARGET"
    fi
    exit 0
fi

for file in "${FILES[@]}"; do
    if $CHECK_BARE_RETURN; then
        check_bare_return_err "$file"
    fi
    check_log_and_return "$file"
done

# Truncation
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
        IFS='|' read -r location rule message <<< "$entry"
        file="${location%%:*}"
        line="${location#*:}"
        $first || echo ","
        first=false
        printf '    {"file":"%s","line":%s,"rule":"%s","message":"%s"}' \
            "$(json_escape "$file")" "$line" "$(json_escape "$rule")" "$(json_escape "$message")"
    done
    echo ""
    echo "  ],"
    printf '  "total": %d,\n' "$TOTAL"
    printf '  "truncated": %s\n' "$TRUNCATED"
    echo "}"
else
    if [[ $TOTAL -eq 0 ]]; then
        echo "No error handling anti-patterns found."
        exit 0
    fi

    echo "Error handling anti-patterns found:"
    echo ""
    for entry in "${FINDINGS[@]}"; do
        IFS='|' read -r location rule message <<< "$entry"
        printf "  %s  [%s] %s\n" "$location" "$rule" "$message"
    done
    if $TRUNCATED; then
        echo "  ... and $((TOTAL - LIMIT)) more (use --limit to adjust)"
    fi
    echo ""
    echo "Total: $TOTAL finding(s)"
fi

if [[ $TOTAL -gt 0 ]]; then
    exit 1
fi
exit 0
