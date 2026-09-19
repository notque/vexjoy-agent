#!/usr/bin/env bash
set -euo pipefail

# Checks that json.NewDecoder calls use DisallowUnknownFields().
# Rule: sapcc requires strict JSON parsing for request bodies.

VERSION="1.0.0"
SCRIPT_NAME="$(basename "$0")"

usage() {
    cat <<EOF
$SCRIPT_NAME v$VERSION — Check for json.NewDecoder without DisallowUnknownFields

USAGE
    bash $SCRIPT_NAME [options] [path]

DESCRIPTION
    Scans Go source files for json.NewDecoder() calls and checks
    that DisallowUnknownFields() is called before Decode().

    Exits 0 if all decoders are strict, 1 if violations found, 2 on error.

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

check_file() {
    local file="$1"
    local decoder_line=0
    local found_decoder=false
    local found_disallow=false
    local line_num=0

    while IFS= read -r line; do
        line_num=$((line_num + 1))

        # Detect json.NewDecoder
        if [[ "$line" =~ json\.NewDecoder ]]; then
            # If we had a previous decoder without disallow, report it
            if $found_decoder && ! $found_disallow; then
                FINDINGS+=("${file}:${decoder_line}|json.NewDecoder without DisallowUnknownFields()")
            fi
            found_decoder=true
            found_disallow=false
            decoder_line=$line_num
        fi

        # Check for DisallowUnknownFields
        if $found_decoder && [[ "$line" =~ DisallowUnknownFields ]]; then
            found_disallow=true
        fi

        # Check for Decode call — if we hit Decode before DisallowUnknownFields, that's a violation
        if $found_decoder && ! $found_disallow && [[ "$line" =~ \.Decode\( ]]; then
            FINDINGS+=("${file}:${decoder_line}|json.NewDecoder without DisallowUnknownFields() before Decode()")
            found_decoder=false
        fi

        # Reset on Decode after DisallowUnknownFields (correct usage)
        if $found_decoder && $found_disallow && [[ "$line" =~ \.Decode\( ]]; then
            found_decoder=false
        fi
    done < "$file"

    # Handle trailing decoder without disallow
    if $found_decoder && ! $found_disallow; then
        FINDINGS+=("${file}:${decoder_line}|json.NewDecoder without DisallowUnknownFields()")
    fi
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
    if grep -q 'json\.NewDecoder' "$file" 2>/dev/null; then
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
        echo "All json.NewDecoder calls use DisallowUnknownFields()."
        exit 0
    fi
    echo "Missing DisallowUnknownFields():"
    echo ""
    for entry in "${FINDINGS[@]}"; do
        IFS='|' read -r location message <<< "$entry"
        printf "  %s  %s\n" "$location" "$message"
    done
    if $TRUNCATED; then
        echo "  ... and $((TOTAL - LIMIT)) more"
    fi
    echo ""
    echo "Total: $TOTAL violation(s)"
fi

[[ $TOTAL -gt 0 ]] && exit 1
exit 0
