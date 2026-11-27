"""Regression tests for skills/content/image-gen/scripts/."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
GENERATE_IMAGE_PATH = SCRIPTS_DIR / "generate_image.py"
NANO_BANANA_PATH = SCRIPTS_DIR / "nano-banana-generate.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_nano_banana_help_works_without_google_genai() -> None:
    proc = subprocess.run(
        [sys.executable, str(NANO_BANANA_PATH), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Generate images using Gemini Nano Banana APIs" in proc.stdout


def test_generate_image_accepts_google_api_key_fallback_and_guards_empty_parts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load("image_gen_generate_image", GENERATE_IMAGE_PATH)
    captured: dict[str, object] = {}

    class FakeModels:
        def generate_content(self, **_kwargs):
            return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=None))])

    class FakeClient:
        def __init__(self, api_key=None):
            captured["used"] = api_key
            self.models = FakeModels()

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "fallback-env-val")
    monkeypatch.setattr(mod, "genai", SimpleNamespace(Client=FakeClient))
    monkeypatch.setattr(mod, "types", SimpleNamespace(GenerateContentConfig=lambda **kw: kw))

    ok = mod.generate_image("a cat", tmp_path / "out.png", "gemini-2.5-flash-image", retries=1)
    assert ok is False
    assert captured["used"] == "fallback-env-val"


def test_nano_banana_guards_none_parts_and_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load("image_gen_nano_banana", NANO_BANANA_PATH)
    monkeypatch.setattr(
        mod,
        "types",
        SimpleNamespace(
            GenerateContentConfig=lambda **kw: kw,
            ImageConfig=lambda **kw: kw,
        ),
    )

    for candidate in (
        SimpleNamespace(finish_reason="STOP", content=SimpleNamespace(parts=None)),
        SimpleNamespace(finish_reason="STOP", content=None),
    ):
        client = SimpleNamespace(
            models=SimpleNamespace(generate_content=lambda cand=candidate, **_kw: SimpleNamespace(candidates=[cand]))
        )
        ok = mod.generate_single(client, "prompt", tmp_path / "out.png")
        assert ok is False


def test_nano_banana_batch_rejects_path_traversal_item_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load("image_gen_nano_banana_batch", NANO_BANANA_PATH)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {"id": "../escape", "prompt": "bad"},
                {"id": "sub/nested", "prompt": "bad"},
                {"id": r"..\win_escape", "prompt": "bad"},
                {"id": "good_sprite", "prompt": "ok"},
            ]
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    called_paths: list[Path] = []

    monkeypatch.setattr(mod, "get_client", lambda: object())

    def fake_generate_single(_client, *, prompt: str, output_path: Path, **_kwargs) -> bool:
        del prompt
        called_paths.append(output_path)
        return True

    monkeypatch.setattr(mod, "generate_single", fake_generate_single)

    args = argparse.Namespace(
        manifest=str(manifest),
        output_dir=str(out_dir),
        originals_dir=None,
        skip_existing=False,
        variants=1,
        delay=0,
        model="flash",
        aspect_ratio=None,
    )
    rc = mod.cmd_batch(args)
    assert rc == 1
    assert called_paths == [(out_dir / "good_sprite.png").resolve()]
