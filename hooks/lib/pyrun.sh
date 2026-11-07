#!/bin/sh
# Run a toolkit hook with python 3.10+: sh "$HOME/.claude/hooks/lib/pyrun.sh" <hook.py> [args]
#
# Every hook command goes through this script, so the command string holds no
# machine path (the repo and installed settings stay identical, and Claude Code
# dedupes them) and its first path is inside hooks/ (every vexinstall version
# owns the entry). Order: the installer pin, python3.14..python3.10 on PATH,
# /opt/homebrew/bin/python3, /usr/local/bin/python3, then python3. Shims are
# skipped: a pyenv shim for a missing version exits 127, which fails open. A
# pick older than 3.10 still meets the guard at the top of every hook, which
# re-execs under a python3.1x or blocks. Layout: docs/installer-layout.md.

p="$HOME/.claude/vexjoy/bin/python3"
if [ -L "$p" ]; then
    [ -x "$p" ] && exec "$p" "$@"
elif [ -f "$p" ] && [ -x "$p" ]; then
    # A regular file here is a script pin (hosts that refuse symlinks) that names its python on line 3.
    # Exec that python directly, and only while it exists (as a dangling symlink fails -x), so the
    # fallbacks below still run and the sync hook can repair the pin. A file naming no absolute
    # python is never run.
    t=
    n=0
    while [ "$n" -lt 3 ] && IFS= read -r line; do
        n=$((n + 1))
        case $line in
            "# vexjoy-python-target: "*)
                t=${line#"# vexjoy-python-target: "}
                break
                ;;
        esac
    done <"$p"
    case $t in
        /* | [A-Za-z]:/*) [ -x "$t" ] && exec "$t" "$@" ;;
    esac
fi
for name in python3.14 python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    p=$(command -v "$name" 2>/dev/null) || continue
    case "$p" in
        */shims/*) continue ;;
    esac
    [ -x "$p" ] && exec "$p" "$@"
done
exec python3 "$@"
