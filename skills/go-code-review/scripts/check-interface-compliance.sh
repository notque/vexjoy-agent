#!/usr/bin/env bash
set -euo pipefail

VERSION="1.0.0"
SCRIPT_NAME="$(basename "$0")"

usage() {
    cat <<EOF
$SCRIPT_NAME v$VERSION — Check for missing compile-time interface compliance verifications

USAGE
    bash $SCRIPT_NAME [options] [path]

DESCRIPTION
    Scans Go files for exported interface definitions and checks whether each
    has a corresponding compile-time compliance assertion like:

        var _ MyInterface = (*MyImpl)(nil)
        var _ MyInterface = MyImpl{}

    Reports interfaces that lack such compile-time checks. This helps catch
    interface drift at compile time instead of runtime.

    Exits 0 if all interfaces are verified, 1 if missing checks found, 2 on error.

OPTIONS
    -h, --help       Show this help message
    -v, --version    Show version
    --json           Output results as JSON
    --include-test   Also scan _test.go files for compliance checks
    --limit N        Show at most N results (default: all)

ARGUMENTS
    path             Directory to scan (default: current directory)

EXAMPLES
    bash $SCRIPT_NAME
    bash $SCRIPT_NAME ./pkg/storage
    bash $SCRIPT_NAME --json .
    bash $SCRIPT_NAME --include-test ./internal
EOF
}

JSON_OUTPUT=false
INCLUDE_TEST=false
LIMIT=0
TARGET=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)       usage; exit 0 ;;
        -v|--version)    echo "$SCRIPT_NAME v$VERSION"; exit 0 ;;
        --json)          JSON_OUTPUT=true; shift ;;
        --include-test)  INCLUDE_TEST=true; shift ;;
        --limit)         LIMIT="${2:?error: --limit requires a number}"; shift 2 ;;
        -*)              echo "error: unknown option: $1" >&2; usage >&2; exit 2 ;;
        *)               TARGET="$1"; shift ;;
    esac
done

TARGET="${TARGET:-.}"

if ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
    echo "error: --limit must be a non-negative integer, got: $LIMIT" >&2
    exit 2
fi

if [[ ! -d "$TARGET" && ! -f "$TARGET" ]]; then
    # Handle ./... patterns
    dir="${TARGET%%/...}"
    dir="${dir:-.}"
    if [[ ! -d "$dir" ]]; then
        echo "error: path not found: $TARGET" >&2
        exit 2
    fi
    TARGET="$dir"
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

# Collect all Go source files
find_go_files() {
    local t="$1"
    if $INCLUDE_TEST; then
        find "$t" -name '*.go' ! -path '*/vendor/*' ! -path '*/.git/*' 2>/dev/null
    else
        find "$t" -name '*.go' ! -name '*_test.go' ! -path '*/vendor/*' ! -path '*/.git/*' 2>/dev/null
    fi
}

# Collect all Go files (including tests) for checking compliance vars
find_all_go_files() {
    find "$1" -name '*.go' ! -path '*/vendor/*' ! -path '*/.git/*' 2>/dev/null
}

# Step 1: Find all exported interface definitions
IFACE_NAMES=()
IFACE_LOCATIONS=()

while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    line_num=0
    while IFS= read -r line; do
        line_num=$((line_num + 1))
        # Match: type ExportedName interface {
        pat='^[[:space:]]*type[[:space:]]+([A-Z][a-zA-Z0-9]*)[[:space:]]+interface[[:space:]]*\{'
        if [[ "$line" =~ $pat ]]; then
            iface_name="${BASH_REMATCH[1]}"
            IFACE_NAMES+=("$iface_name")
            IFACE_LOCATIONS+=("$file:$line_num")
        fi
    done < "$file"
done < <(find_go_files "$TARGET")

if [[ ${#IFACE_NAMES[@]} -eq 0 ]]; then
    if $JSON_OUTPUT; then
        echo '{"interfaces":[],"missing":[],"count_interfaces":0,"count_missing":0}'
    else
        echo "No exported interfaces found in: $TARGET"
    fi
    exit 0
fi

# Step 2: Scan all Go files (including tests) for compliance checks
# Pattern: var _ InterfaceName = ...
ALL_GO_FILES=()
while IFS= read -r f; do
    [[ -n "$f" ]] && ALL_GO_FILES+=("$f")
done < <(find_all_go_files "$TARGET")

MISSING=()

for ((i=0; i<${#IFACE_NAMES[@]}; i++)); do
    iface_name="${IFACE_NAMES[$i]}"
    location="${IFACE_LOCATIONS[$i]}"
    # Look for: var _ InterfaceName = (various patterns)
    if ! grep -qlE "var[[:space:]]+_[[:space:]]+${iface_name}[[:space:]]*=" \
         "${ALL_GO_FILES[@]}" 2>/dev/null; then
        MISSING+=("${iface_name}|${location}")
    fi
done

# Sort for stable output
IFS=$'\n' MISSING=($(sort <<<"${MISSING[*]}")); unset IFS

# Truncation
TOTAL=${#MISSING[@]}
TRUNCATED=false
if [[ $LIMIT -gt 0 && $TOTAL -gt $LIMIT ]]; then
    MISSING=("${MISSING[@]:0:$LIMIT}")
    TRUNCATED=true
fi

# Output results
if $JSON_OUTPUT; then
    echo "{"
    echo '  "interfaces": ['
    first=true
    SORTED_INDICES=()
    for ((i=0; i<${#IFACE_NAMES[@]}; i++)); do
        SORTED_INDICES+=("$i|${IFACE_NAMES[$i]}")
    done
    IFS=$'\n' SORTED_INDICES=($(sort -t'|' -k2 <<<"${SORTED_INDICES[*]}")); unset IFS

    for entry in "${SORTED_INDICES[@]}"; do
        i="${entry%%|*}"
        iface_name="${IFACE_NAMES[$i]}"
        location="${IFACE_LOCATIONS[$i]}"
        file="${location%%:*}"
        line="${location#*:}"
        $first || echo ","
        first=false
        printf '    {"name":"%s","file":"%s","line":%s}' "$(json_escape "$iface_name")" "$(json_escape "$file")" "$line"
    done
    echo ""
    echo "  ],"
    echo '  "missing": ['
    first=true
    for entry in "${MISSING[@]+"${MISSING[@]}"}"; do
        IFS='|' read -r name location <<< "$entry"
        file="${location%%:*}"
        line="${location#*:}"
        $first || echo ","
        first=false
        printf '    {"name":"%s","file":"%s","line":%s}' "$(json_escape "$name")" "$(json_escape "$file")" "$line"
    done
    echo ""
    echo "  ],"
    printf '  "count_interfaces": %d,\n' "${#IFACE_NAMES[@]}"
    printf '  "count_missing": %d,\n' "$TOTAL"
    printf '  "truncated": %s\n' "$TRUNCATED"
    echo "}"
else
    echo "Exported interfaces found: ${#IFACE_NAMES[@]}"
    echo ""

    if [[ $TOTAL -eq 0 ]]; then
        echo "All interfaces have compile-time compliance checks."
        exit 0
    fi

    echo "Missing compile-time compliance checks:"
    echo ""
    for entry in "${MISSING[@]}"; do
        IFS='|' read -r name location <<< "$entry"
        printf "  %s  interface '%s' has no 'var _ %s = ...' assertion\n" "$location" "$name" "$name"
    done
    if $TRUNCATED; then
        echo "  ... and $((TOTAL - LIMIT)) more (use --limit to adjust)"
    fi
    echo ""
    echo "Add compile-time checks like:"
    echo "  var _ MyInterface = (*MyImpl)(nil)"
    echo ""
    echo "Total: $TOTAL interface(s) missing verification"
fi

if [[ $TOTAL -gt 0 ]]; then
    exit 1
fi
exit 0
