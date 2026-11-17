"""Tests for scripts/voice-triad-eval.py.

All corpus fixtures use invented text only.  No real author names or samples.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    """Load voice-triad-eval.py as a module."""
    spec = importlib.util.spec_from_file_location("voice_triad_eval", REPO_ROOT / "scripts" / "voice-triad-eval.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_corpus(tmp_path: Path, count: int, *, prefix: str = "piece") -> Path:
    """Create a corpus directory with *count* .md files of invented text."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for i in range(count):
        (corpus / f"{prefix}-{i:03d}.md").write_text(
            f"Lorem ipsum piece number {i}. Sed ut perspiciatis unde omnis iste natus error sit.\n"
        )
    return corpus


def _run_split(tmp_path: Path, corpus: Path, **kwargs) -> tuple[int, Path]:
    """Run the split subcommand and return (exit_code, manifest_path)."""
    manifest = tmp_path / "manifest.json"
    argv = ["split", "--corpus", str(corpus), "--out", str(manifest)]
    for k, v in kwargs.items():
        flag = f"--{k.replace('_', '-')}"
        if isinstance(v, bool):
            if v:
                argv.append(flag)
        else:
            argv.extend([flag, str(v)])
    code = MOD.main(argv)
    return code, manifest


# ---------------------------------------------------------------------------
# split: determinism and holdout floor
# ---------------------------------------------------------------------------


class TestSplit:
    """Tests for the split subcommand."""

    def test_deterministic_with_same_seed(self, tmp_path: Path) -> None:
        """Two runs with the same seed produce identical manifests."""
        corpus = _make_corpus(tmp_path, 15)
        _, m1 = _run_split(tmp_path / "r1", corpus, seed=42)
        _, m2 = _run_split(tmp_path / "r2", corpus, seed=42)
        assert json.loads(m1.read_text())["holdout"] == json.loads(m2.read_text())["holdout"]
        assert json.loads(m1.read_text())["train"] == json.loads(m2.read_text())["train"]

    def test_different_seed_different_split(self, tmp_path: Path) -> None:
        """Different seeds produce different holdout sets (with enough pieces)."""
        corpus = _make_corpus(tmp_path, 20)
        _, m1 = _run_split(tmp_path / "r1", corpus, seed=0)
        _, m2 = _run_split(tmp_path / "r2", corpus, seed=99)
        h1 = {e["name"] for e in json.loads(m1.read_text())["holdout"]}
        h2 = {e["name"] for e in json.loads(m2.read_text())["holdout"]}
        assert h1 != h2

    def test_holdout_floor_enforced(self, tmp_path: Path) -> None:
        """Holdout has at least min_holdout pieces when corpus is large enough."""
        corpus = _make_corpus(tmp_path, 15)
        _, m = _run_split(tmp_path / "out", corpus, min_holdout=5)
        manifest = json.loads(m.read_text())
        assert len(manifest["holdout"]) >= 5

    def test_refuses_under_8_pieces(self, tmp_path: Path) -> None:
        """Exit 2 when the corpus has fewer than 8 pieces."""
        corpus = _make_corpus(tmp_path, 7)
        code, _ = _run_split(tmp_path / "out", corpus)
        assert code == 2

    def test_accepts_exactly_8_pieces(self, tmp_path: Path) -> None:
        """Exit 0 when the corpus has exactly 8 pieces."""
        corpus = _make_corpus(tmp_path, 8)
        code, _ = _run_split(tmp_path / "out", corpus)
        assert code == 0

    def test_recent_first_puts_newest_in_holdout(self, tmp_path: Path) -> None:
        """With --recent-first, date-prefixed newest files land in holdout."""
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        dates = [
            "2024-01-01",
            "2024-02-01",
            "2024-03-01",
            "2024-04-01",
            "2024-05-01",
            "2024-06-01",
            "2024-07-01",
            "2024-08-01",
            "2024-09-01",
            "2024-10-01",
            "2024-11-01",
            "2024-12-01",
        ]
        for d in dates:
            (corpus / f"{d}-post.md").write_text(f"Content for {d}.\n")

        _, m = _run_split(
            tmp_path / "out",
            corpus,
            recent_first=True,
            holdout_frac=0.3,
            min_holdout=3,
        )
        manifest = json.loads(m.read_text())
        holdout_names = {e["name"] for e in manifest["holdout"]}
        # The 3-4 newest dates should be in holdout.
        assert "2024-12-01-post.md" in holdout_names
        assert "2024-11-01-post.md" in holdout_names
        assert "2024-10-01-post.md" in holdout_names

    def test_sha256_in_manifest(self, tmp_path: Path) -> None:
        """Every entry has a sha256 that matches the file content."""
        corpus = _make_corpus(tmp_path, 10)
        _, m = _run_split(tmp_path / "out", corpus)
        manifest = json.loads(m.read_text())
        for entry in manifest["train"] + manifest["holdout"]:
            path = corpus / entry["name"]
            assert entry["sha256"] == MOD._sha256(path)


# ---------------------------------------------------------------------------
# judge-jobs: both orders, no arm names in prompt
# ---------------------------------------------------------------------------


class TestJudgeJobs:
    """Tests for the judge-jobs subcommand."""

    def _setup_drafts(self, tmp_path: Path, corpus: Path, manifest_path: Path, arm_a: str, arm_b: str) -> Path:
        """Create draft files for all holdout pieces."""
        manifest = json.loads(manifest_path.read_text())
        drafts = tmp_path / "drafts"
        for idx, arm in enumerate((arm_a, arm_b)):
            arm_dir = drafts / arm
            arm_dir.mkdir(parents=True)
            for entry in manifest["holdout"]:
                pid = Path(entry["name"]).stem
                (arm_dir / f"{pid}.md").write_text(f"Draft text for {pid} variant {idx}.\n")
        return drafts

    def test_writes_both_orders(self, tmp_path: Path) -> None:
        """Each holdout piece gets an AB and a BA job."""
        corpus = _make_corpus(tmp_path, 10)
        _, m = _run_split(tmp_path / "split", corpus)
        drafts = self._setup_drafts(tmp_path, corpus, m, "skill-v1", "baseline")

        jobs_dir = tmp_path / "jobs"
        code = MOD.main(
            [
                "judge-jobs",
                "--manifest",
                str(m),
                "--corpus",
                str(corpus),
                "--drafts",
                str(drafts),
                "--arms",
                "skill-v1",
                "baseline",
                "--out",
                str(jobs_dir),
            ]
        )
        assert code == 0

        job_files = sorted(jobs_dir.iterdir())
        manifest = json.loads(m.read_text())
        holdout_count = len(manifest["holdout"])
        assert len(job_files) == holdout_count * 2

        # Check that each piece has both AB and BA.
        ids = [json.loads(f.read_text())["id"] for f in job_files]
        for entry in manifest["holdout"]:
            pid = Path(entry["name"]).stem
            assert f"judge-{pid}-AB" in ids
            assert f"judge-{pid}-BA" in ids

    def test_prompt_does_not_name_arms(self, tmp_path: Path) -> None:
        """The judge prompt says Draft 1 and Draft 2, never the arm names."""
        corpus = _make_corpus(tmp_path, 10)
        _, m = _run_split(tmp_path / "split", corpus)
        drafts = self._setup_drafts(tmp_path, corpus, m, "my-skill", "no-skill")

        jobs_dir = tmp_path / "jobs"
        MOD.main(
            [
                "judge-jobs",
                "--manifest",
                str(m),
                "--corpus",
                str(corpus),
                "--drafts",
                str(drafts),
                "--arms",
                "my-skill",
                "no-skill",
                "--out",
                str(jobs_dir),
            ]
        )

        for f in jobs_dir.iterdir():
            job = json.loads(f.read_text())
            prompt = job["prompt"]
            assert "my-skill" not in prompt
            assert "no-skill" not in prompt
            assert "Draft 1" in prompt
            assert "Draft 2" in prompt

    def test_missing_draft_errors(self, tmp_path: Path) -> None:
        """Exit 2 when a draft file is missing."""
        corpus = _make_corpus(tmp_path, 10)
        _, m = _run_split(tmp_path / "split", corpus)
        # Create drafts for arm_a only.
        manifest = json.loads(m.read_text())
        drafts = tmp_path / "drafts"
        (drafts / "arm-a").mkdir(parents=True)
        for entry in manifest["holdout"]:
            pid = Path(entry["name"]).stem
            (drafts / "arm-a" / f"{pid}.md").write_text("Draft A.\n")
        # arm-b dir missing entirely.
        (drafts / "arm-b").mkdir(parents=True)

        code = MOD.main(
            [
                "judge-jobs",
                "--manifest",
                str(m),
                "--corpus",
                str(corpus),
                "--drafts",
                str(drafts),
                "--arms",
                "arm-a",
                "arm-b",
                "--out",
                str(tmp_path / "jobs"),
            ]
        )
        assert code == 2


# ---------------------------------------------------------------------------
# score: arm mapping, consistency, first-position rate
# ---------------------------------------------------------------------------


class TestScore:
    """Tests for the score subcommand."""

    def _make_jobs_and_judgments(
        self,
        tmp_path: Path,
        piece_ids: list[str],
        arm_a: str,
        arm_b: str,
        judge_fn,
    ) -> tuple[Path, Path]:
        """Build job files and a judgments JSONL from a judge function.

        judge_fn(order, piece_id) -> int (1 or 2).
        """
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        lines: list[str] = []

        for pid in piece_ids:
            for order, first, second in [("AB", arm_a, arm_b), ("BA", arm_b, arm_a)]:
                jid = f"judge-{pid}-{order}"
                job = {
                    "id": jid,
                    "piece_id": pid,
                    "order": order,
                    "first_arm": first,
                    "second_arm": second,
                    "prompt": "...",
                }
                (jobs_dir / f"{jid}.json").write_text(json.dumps(job) + "\n")
                closer = judge_fn(order, pid)
                judgment = {
                    "id": jid,
                    "closer": closer,
                    "note_draft_1": f"note about draft 1 in {order}",
                    "note_draft_2": f"note about draft 2 in {order}",
                }
                lines.append(json.dumps(judgment))

        judgments_path = tmp_path / "judgments.jsonl"
        judgments_path.write_text("\n".join(lines) + "\n")
        return jobs_dir, judgments_path

    def test_always_pick_1_yields_zero_consistency(self, tmp_path: Path) -> None:
        """A judge that always picks Draft 1 yields consistency 0 and first-position rate 1.0.

        In AB order, Draft 1 = arm_a, so closer=1 -> arm_a wins.
        In BA order, Draft 1 = arm_b, so closer=1 -> arm_b wins.
        The two orders disagree on every piece -> consistency 0.
        """
        pieces = [f"p{i}" for i in range(5)]
        jobs, jfile = self._make_jobs_and_judgments(tmp_path, pieces, "A", "B", lambda _order, _pid: 1)
        code = MOD.main(["score", "--jobs", str(jobs), "--judgments", str(jfile), "--json"])
        assert code == 0

        # Re-run to capture output.
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            MOD.main(["score", "--jobs", str(jobs), "--judgments", str(jfile), "--json"])
        result = json.loads(buf.getvalue())
        assert result["consistency"] == 0.0
        assert result["first_position_rate"] == 1.0

    def test_consistent_judge_yields_consistency_1(self, tmp_path: Path) -> None:
        """A judge that always picks arm_a (position varies) yields consistency 1.0."""
        pieces = [f"p{i}" for i in range(5)]

        def pick_a(order: str, pid: str) -> int:
            # In AB: arm_a is Draft 1 -> return 1.
            # In BA: arm_a is Draft 2 -> return 2.
            return 1 if order == "AB" else 2

        jobs, jfile = self._make_jobs_and_judgments(tmp_path, pieces, "A", "B", pick_a)

        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            MOD.main(["score", "--jobs", str(jobs), "--judgments", str(jfile), "--json"])
        result = json.loads(buf.getvalue())
        assert result["consistency"] == 1.0

    def test_maps_closer_to_correct_arm(self, tmp_path: Path) -> None:
        """Score correctly maps closer=1 and closer=2 to the right arm names."""
        pieces = ["x"]

        def pick_second(order: str, pid: str) -> int:
            return 2  # always pick Draft 2

        jobs, jfile = self._make_jobs_and_judgments(tmp_path, pieces, "alpha", "beta", pick_second)

        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            MOD.main(["score", "--jobs", str(jobs), "--judgments", str(jfile), "--json"])
        result = json.loads(buf.getvalue())
        # AB order: Draft 2 = beta -> beta wins.
        # BA order: Draft 2 = alpha -> alpha wins.
        # Both orders disagree -> split.
        assert result["piece_results"]["x"] == "split"

    def test_incomplete_judgments_exit_2(self, tmp_path: Path) -> None:
        """Exit 2 when some judgments are missing."""
        pieces = ["q1", "q2"]
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        for pid in pieces:
            for order, first, second in [("AB", "A", "B"), ("BA", "B", "A")]:
                jid = f"judge-{pid}-{order}"
                job = {
                    "id": jid,
                    "piece_id": pid,
                    "order": order,
                    "first_arm": first,
                    "second_arm": second,
                    "prompt": "...",
                }
                (jobs_dir / f"{jid}.json").write_text(json.dumps(job) + "\n")

        # Only provide judgments for q1.
        judgments_path = tmp_path / "judgments.jsonl"
        judgments_path.write_text(
            json.dumps({"id": "judge-q1-AB", "closer": 1, "note_draft_1": "", "note_draft_2": ""})
            + "\n"
            + json.dumps({"id": "judge-q1-BA", "closer": 2, "note_draft_1": "", "note_draft_2": ""})
            + "\n"
        )
        code = MOD.main(["score", "--jobs", str(jobs_dir), "--judgments", str(judgments_path)])
        assert code == 2


# ---------------------------------------------------------------------------
# distill: flags ratio < 1.0
# ---------------------------------------------------------------------------


class TestDistill:
    """Tests for the distill subcommand."""

    def test_flags_ratio_under_1(self, tmp_path: Path) -> None:
        """A brief shorter than its final gets flagged."""
        briefs = tmp_path / "briefs"
        finals = tmp_path / "finals"
        briefs.mkdir()
        finals.mkdir()
        (briefs / "doc-a.md").write_text("short brief\n")
        (finals / "doc-a.md").write_text("this is a much longer final draft with many more words than the brief\n")

        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            MOD.main(["distill", "--briefs", str(briefs), "--finals", str(finals), "--json"])
        rows = json.loads(buf.getvalue())
        assert len(rows) == 1
        assert rows[0]["flagged"] is True
        assert rows[0]["ratio"] < 1.0

    def test_ratio_above_1_not_flagged(self, tmp_path: Path) -> None:
        """A brief longer than its final is not flagged."""
        briefs = tmp_path / "briefs"
        finals = tmp_path / "finals"
        briefs.mkdir()
        finals.mkdir()
        (briefs / "doc-b.md").write_text(
            "this is a very long substance brief with all the facts and quotes and details needed " * 5 + "\n"
        )
        (finals / "doc-b.md").write_text("short final\n")

        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            MOD.main(["distill", "--briefs", str(briefs), "--finals", str(finals), "--json"])
        rows = json.loads(buf.getvalue())
        assert len(rows) == 1
        assert rows[0]["flagged"] is False
        assert rows[0]["ratio"] > 1.0
