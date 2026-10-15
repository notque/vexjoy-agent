"""Tables and survivor lists from the run data."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .runner import load_results


def per_target(results: dict[str, dict], deny: dict[str, bool]) -> list[dict]:
    """Return one summary row per target."""
    rows = []
    for name, data in sorted(results.items()):
        counts = Counter(r["status"] for r in data["rows"])
        kinds = Counter(r["kind"] for r in data["rows"] if r["status"] == "killed")
        base = data["baseline"]
        generated = len(data["rows"])
        killed = counts["killed"]
        survived = counts["survived"]
        cnr = counts["could_not_run"]
        scored = killed + survived
        rows.append(
            {
                "name": name,
                "deny": deny.get(name, False),
                "usable": base["usable"],
                "reason": "" if base["usable"] else base["reason"],
                "generated": generated,
                "killed": killed,
                "timeouts": kinds["timeout"],
                "survived": survived,
                "could_not_run": cnr,
                "kill_rate": (killed / scored) if scored else None,
                "flaky": len(base["flaky"]),
                "unparseable_rejected": data["meta"].get("rejected_unparseable"),
                "anchor_errors": len(data["meta"].get("anchor_errors", [])),
            }
        )
    return rows


def markdown_table(rows: list[dict]) -> str:
    """Return the per-target table as markdown."""
    head = "| target | deny | mutants | killed | survived | could_not_run | kill rate | flaky dropped |\n|---|---|---|---|---|---|---|---|\n"
    lines = []
    for r in rows:
        if not r["usable"]:
            lines.append(
                f"| {r['name']} | {'y' if r['deny'] else ''} | 0 | 0 | 0 | could_not_run | n/a | {r['flaky']} |"
            )
            continue
        rate = f"{r['kill_rate']:.2f}" if r["kill_rate"] is not None else "n/a"
        lines.append(
            f"| {r['name']} | {'y' if r['deny'] else ''} | {r['generated']} | {r['killed']} | {r['survived']} | "
            f"{r['could_not_run']} | {rate} | {r['flaky']} |"
        )
    return head + "\n".join(lines)


def operator_table(results: dict[str, dict]) -> str:
    """Return the operator breakdown as markdown."""
    stats: dict[str, Counter] = defaultdict(Counter)
    for data in results.values():
        for row in data["rows"]:
            stats[row["operator"]][row["status"]] += 1
    out = "| operator | mutants | killed | survived | kill rate |\n|---|---|---|---|---|\n"
    for op, c in sorted(stats.items()):
        total = c["killed"] + c["survived"]
        cells = [op, sum(c.values()), c["killed"], c["survived"], f"{c['killed'] / total:.2f}"]
        out += "| " + " | ".join(str(x) for x in cells) + " |\n"
    return out


def survivors(results: dict[str, dict]) -> list[dict]:
    """Return every surviving mutant as a flat row with its target name."""
    out = []
    for name, data in sorted(results.items()):
        for row in data["rows"]:
            if row["status"] == "survived":
                out.append(
                    {
                        "target": name,
                        **{k: row[k] for k in ("id", "operator", "line", "function", "description", "diff")},
                    }
                )
    return out


def format_survivors(rows: list[dict]) -> str:
    """Return the survivor list as plain text, one block per mutant."""
    if not rows:
        return "no surviving mutants"
    blocks = []
    for r in rows:
        where = f"{r['target']}:{r['line']}" + (f" in {r['function']}" if r["function"] else "")
        blocks.append(f"SURVIVED {where} [{r['operator']}] {r['description']}\n{r['diff'].rstrip()}")
    return "\n\n".join(blocks)


def main(cache: Path, deny: dict[str, bool], names: set[str] | None = None) -> None:
    """Print the tables."""
    results = load_results(cache)
    if names is not None:
        results = {n: d for n, d in results.items() if n in names}
    rows = per_target(results, deny)
    print(markdown_table(rows))
    print()
    print(operator_table(results))
    usable = [r for r in rows if r["usable"]]
    total = sum(r["generated"] for r in usable)
    killed = sum(r["killed"] for r in usable)
    survived = sum(r["survived"] for r in usable)
    scored = killed + survived
    rate = f"{killed / scored:.3f}" if scored else "n/a"
    print(
        f"targets {len(rows)}, usable {len(usable)}, could_not_run {len(rows) - len(usable)}; mutants {total}, "
        f"killed {killed}, survived {survived}, kill rate {rate}"
    )
    for r in rows:
        if not r["usable"]:
            print(f"could_not_run: {r['name']}: {r['reason']}")
