#!/usr/bin/env bash
set -euo pipefail

VERSION="1.0.0"
SCRIPT_NAME="$(basename "$0")"

usage() {
    cat <<EOF
$SCRIPT_NAME v$VERSION — Generate a table-driven test scaffold for a Go function

USAGE
    bash $SCRIPT_NAME [options] <FuncName> <package>

DESCRIPTION
    Outputs a table-driven test file for the given function and package.
    By default writes to stdout; use --output to write to a file.

    Exits 0 on success, 2 on error.

OPTIONS
    -h, --help           Show this help message
    -v, --version        Show version
    --output FILE        Write to FILE instead of stdout
    --force              Allow --output to overwrite an existing file
    --parallel           Include t.Parallel() in generated test
    --json               Output structured JSON metadata to stdout

ARGUMENTS
    FuncName             Name of the function to test (must be exported/uppercase)
    package              Go package name for the test file

EXAMPLES
    bash $SCRIPT_NAME ParseConfig config
    bash $SCRIPT_NAME --parallel ParseConfig config
    bash $SCRIPT_NAME --output config/parse_config_test.go ParseConfig config
    bash $SCRIPT_NAME --force --output config/parse_config_test.go ParseConfig config
    bash $SCRIPT_NAME --json --output config/parse_config_test.go ParseConfig config
    bash $SCRIPT_NAME ParseConfig config > config/parse_config_test.go
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

OUTPUT=""
PARALLEL=false
JSON_OUTPUT=false
FORCE=false
POSITIONAL=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)    usage; exit 0 ;;
        -v|--version) echo "$SCRIPT_NAME v$VERSION"; exit 0 ;;
        --output)     OUTPUT="${2:?error: --output requires a file path}"; shift 2 ;;
        --force)      FORCE=true; shift ;;
        --parallel)   PARALLEL=true; shift ;;
        --json)       JSON_OUTPUT=true; shift ;;
        -*)           echo "error: unknown option: $1" >&2; usage >&2; exit 2 ;;
        *)            POSITIONAL+=("$1"); shift ;;
    esac
done

if [[ ${#POSITIONAL[@]} -lt 2 ]]; then
    echo "error: FuncName and package are required" >&2
    usage >&2
    exit 2
fi

FUNC="${POSITIONAL[0]}"
PKG="${POSITIONAL[1]}"

if [[ ! "$FUNC" =~ ^[A-Z] ]]; then
    echo "error: FuncName '$FUNC' must start with an uppercase letter" >&2
    exit 2
fi

generate_test() {
    local parallel_top="" parallel_sub=""
    if $PARALLEL; then
        parallel_top=$'\tt.Parallel()\n'
        parallel_sub=$'\t\t\tt.Parallel()\n'
    fi

    cat <<EOF
package ${PKG}

import (
	"testing"
)

func Test${FUNC}(t *testing.T) {
${parallel_top}	tests := []struct {
		name string
		give string // TODO: replace with actual input type
		want string // TODO: replace with actual output type
	}{
		{
			name: "basic case",
			give: "",
			want: "",
		},
		// TODO: add more test cases
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
${parallel_sub}			got := ${FUNC}(tt.give)
			if got != tt.want {
				t.Errorf("${FUNC}(%q) = %q, want %q", tt.give, got, tt.want)
			}
			// For richer diffs, consider:
			//   if diff := cmp.Diff(tt.want, got); diff != "" {
			//       t.Errorf("${FUNC}() mismatch (-want +got):\n%s", diff)
			//   }
		})
	}
}
EOF
}

if [[ -n "$OUTPUT" ]]; then
    OUTPUT_DIR="$(dirname "$OUTPUT")"
    if [[ ! -d "$OUTPUT_DIR" ]]; then
        echo "error: directory '$OUTPUT_DIR' does not exist" >&2
        exit 2
    fi
    if [[ -f "$OUTPUT" ]] && ! $FORCE; then
        echo "error: '$OUTPUT' already exists (use --force to overwrite)" >&2
        exit 2
    fi
    generate_test > "$OUTPUT"
    if $JSON_OUTPUT; then
        FUNC_ESC="$(json_escape "$FUNC")"
        PKG_ESC="$(json_escape "$PKG")"
        OUTPUT_ESC="$(json_escape "$OUTPUT")"
        cat <<EOF
{"func":"$FUNC_ESC","package":"$PKG_ESC","output_file":"$OUTPUT_ESC","parallel":$PARALLEL,"written":true}
EOF
    else
        echo "Wrote test scaffold to $OUTPUT"
    fi
else
    if $JSON_OUTPUT; then
        generate_test >&2
        FUNC_ESC="$(json_escape "$FUNC")"
        PKG_ESC="$(json_escape "$PKG")"
        cat <<EOF
{"func":"$FUNC_ESC","package":"$PKG_ESC","output_file":"","parallel":$PARALLEL,"written":false}
EOF
    else
        generate_test
    fi
fi

exit 0
