#!/usr/bin/env bash
set -euo pipefail

VERSION="1.1.0"
SCRIPT_NAME="$(basename "$0")"

usage() {
    cat <<EOF
$SCRIPT_NAME v$VERSION — Run Go benchmarks with optional comparison

USAGE
    bash $SCRIPT_NAME [options] [package]

DESCRIPTION
    Wrapper around 'go test -bench' that runs benchmarks multiple times and
    optionally compares results against a saved baseline using benchstat.

    Results can be saved to a file for future comparison. If benchstat is
    installed and a baseline is provided, a statistical comparison is shown.

EXIT CODES
    0    Benchmarks ran successfully
    1    go test failed (compilation error, test failure, no benchmarks found)
    2    Usage error (missing arguments, bad flags, file exists without --force)

OPTIONS
    -h, --help           Show this help message
    -v, --version        Show version
    -n, --count N        Number of benchmark iterations (default: 5)
    -b, --baseline FILE  Compare results against this baseline file
    -s, --save FILE      Save benchmark results to this file
    -f, --filter REGEX   Benchmark filter regex (default: ".")
    --json               Output metadata as JSON (human output goes to stderr)
    --benchmem           Include memory allocation stats (default: on)
    --no-benchmem        Disable memory allocation stats
    --force              Allow --save to overwrite existing files
    --limit N            Max benchmark result lines to include (default: 0 = all)

ARGUMENTS
    package              Go package to benchmark (default: ./...)

EXAMPLES
    bash $SCRIPT_NAME
    bash $SCRIPT_NAME -n 10 ./pkg/parser
    bash $SCRIPT_NAME --save baseline.txt ./...
    bash $SCRIPT_NAME --baseline baseline.txt --save current.txt ./...
    bash $SCRIPT_NAME --filter BenchmarkSort -n 3
    bash $SCRIPT_NAME --json --limit 5 ./...
    bash $SCRIPT_NAME --save results.txt --force ./...
EOF
}

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\t'/\\t}"
    s="${s//$'\r'/}"
    s="${s//$'\n'/\\n}"
    printf '%s' "$s"
}

# Print human-readable output: stdout in text mode, stderr in JSON mode.
log() {
    if $JSON_OUTPUT; then
        echo "$@" >&2
    else
        echo "$@"
    fi
}

COUNT=5
BASELINE=""
SAVE=""
FILTER="."
PACKAGE=""
JSON_OUTPUT=false
BENCHMEM=true
FORCE=false
LIMIT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)      usage; exit 0 ;;
        -v|--version)   echo "$SCRIPT_NAME v$VERSION"; exit 0 ;;
        -n|--count)     COUNT="${2:?error: --count requires a number}"; shift 2 ;;
        -b|--baseline)  BASELINE="${2:?error: --baseline requires a file path}"; shift 2 ;;
        -s|--save)      SAVE="${2:?error: --save requires a file path}"; shift 2 ;;
        -f|--filter)    FILTER="${2:?error: --filter requires a regex}"; shift 2 ;;
        --json)         JSON_OUTPUT=true; shift ;;
        --benchmem)     BENCHMEM=true; shift ;;
        --no-benchmem)  BENCHMEM=false; shift ;;
        --force)        FORCE=true; shift ;;
        --limit)        LIMIT="${2:?error: --limit requires a number}"; shift 2 ;;
        -*)             echo "error: unknown option: $1" >&2; usage >&2; exit 2 ;;
        *)              PACKAGE="$1"; shift ;;
    esac
done

PACKAGE="${PACKAGE:-./...}"

if ! command -v go &>/dev/null; then
    echo "error: 'go' command not found in PATH" >&2
    exit 2
fi

if ! [[ "$COUNT" =~ ^[1-9][0-9]*$ ]]; then
    echo "error: --count must be a positive integer, got: $COUNT" >&2
    exit 2
fi

if ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
    echo "error: --limit must be a non-negative integer, got: $LIMIT" >&2
    exit 2
fi

if [[ -n "$BASELINE" && ! -f "$BASELINE" ]]; then
    echo "error: baseline file not found: $BASELINE" >&2
    exit 2
fi

if [[ -n "$SAVE" && -f "$SAVE" ]] && ! $FORCE; then
    echo "error: save target already exists: $SAVE (use --force to overwrite)" >&2
    exit 2
fi

HAS_BENCHSTAT=false
if command -v benchstat &>/dev/null; then
    HAS_BENCHSTAT=true
fi

BENCH_ARGS=(-bench "$FILTER" -count "$COUNT" -run '^$')
if $BENCHMEM; then
    BENCH_ARGS+=(-benchmem)
fi

TMPFILE=$(mktemp "${TMPDIR:-/tmp}/bench-XXXXXX.txt")
trap 'rm -f "$TMPFILE"' EXIT

log "Running benchmarks: go test ${BENCH_ARGS[*]} $PACKAGE"
log "Iterations: $COUNT"
log ""

GO_EXIT=0
if $JSON_OUTPUT; then
    go test "${BENCH_ARGS[@]}" "$PACKAGE" 2>&1 | tee "$TMPFILE" >&2 || GO_EXIT=$?
else
    go test "${BENCH_ARGS[@]}" "$PACKAGE" 2>&1 | tee "$TMPFILE" || GO_EXIT=$?
fi

BENCH_COUNT=$(grep -cE '^Benchmark' "$TMPFILE" || true)

TRUNCATED=false
if [[ $LIMIT -gt 0 && $BENCH_COUNT -gt $LIMIT ]]; then
    TRUNCATED=true
fi

if ! $JSON_OUTPUT && $TRUNCATED; then
    log ""
    log "Note: $BENCH_COUNT benchmark results found, showing first $LIMIT (--limit $LIMIT)"
fi

if [[ -n "$SAVE" ]]; then
    cp "$TMPFILE" "$SAVE"
    log ""
    log "Results saved to: $SAVE"
fi

if [[ -n "$BASELINE" ]]; then
    log ""
    log "=== Comparison with baseline: $BASELINE ==="
    log ""
    if $HAS_BENCHSTAT; then
        if $JSON_OUTPUT; then
            benchstat "$BASELINE" "$TMPFILE" >&2 || true
        else
            benchstat "$BASELINE" "$TMPFILE" || true
        fi
    else
        log "note: install benchstat for statistical comparison:"
        log "  go install golang.org/x/perf/cmd/benchstat@latest"
        log ""
        log "--- Baseline ---"
        if $JSON_OUTPUT; then
            grep -E '^Benchmark' "$BASELINE" >&2 || true
        else
            grep -E '^Benchmark' "$BASELINE" || true
        fi
        log ""
        log "--- Current ---"
        if $JSON_OUTPUT; then
            grep -E '^Benchmark' "$TMPFILE" >&2 || true
        else
            grep -E '^Benchmark' "$TMPFILE" || true
        fi
    fi
fi

FINAL_EXIT=0
if [[ $GO_EXIT -ne 0 ]]; then
    FINAL_EXIT=1
    if ! $JSON_OUTPUT; then
        log ""
        log "error: go test exited with code $GO_EXIT"
    fi
elif [[ $BENCH_COUNT -eq 0 ]]; then
    FINAL_EXIT=1
    if ! $JSON_OUTPUT; then
        log ""
        log "error: no benchmarks found matching filter: $FILTER"
    fi
fi

if $JSON_OUTPUT; then
    BENCH_OUTPUT=$(<"$TMPFILE")
    if $TRUNCATED; then
        limited=""
        bench_seen=0
        while IFS= read -r line; do
            if [[ "$line" =~ ^Benchmark ]]; then
                bench_seen=$((bench_seen + 1))
                if [[ $bench_seen -le $LIMIT ]]; then
                    limited+="$line"$'\n'
                fi
            else
                limited+="$line"$'\n'
            fi
        done < "$TMPFILE"
        BENCH_OUTPUT="$limited"
    fi

    escaped_package=$(json_escape "$PACKAGE")
    escaped_filter=$(json_escape "$FILTER")
    escaped_baseline=$(json_escape "$BASELINE")
    escaped_save=$(json_escape "$SAVE")
    escaped_output=$(json_escape "$BENCH_OUTPUT")

    printf '{"count":%d,' "$COUNT"
    printf '"package":"%s",' "$escaped_package"
    printf '"filter":"%s",' "$escaped_filter"
    printf '"benchmarks_found":%d,' "$BENCH_COUNT"
    printf '"baseline":"%s",' "$escaped_baseline"
    printf '"save":"%s",' "$escaped_save"
    printf '"exit_code":%d,' "$GO_EXIT"
    printf '"output":"%s"' "$escaped_output"
    if $TRUNCATED; then
        printf ',"truncated":true'
    fi
    printf '}\n'
fi

exit $FINAL_EXIT
