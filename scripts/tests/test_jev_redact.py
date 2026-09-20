"""Tests for scripts/jev_redact.py.

All secret-looking values here are obviously fake (repeated X / x characters).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_redact

FAKE_AWS = "AKIA" + "X" * 16
FAKE_ASIA = "ASIA" + "X" * 16
FAKE_GHP = "ghp_" + "x" * 36
FAKE_GHO = "gho_" + "x" * 36
FAKE_OPENAI = "sk-" + "x" * 40
FAKE_STRIPE = "sk_live_" + "x" * 24
FAKE_STRIPE_TEST = "sk_test_" + "x" * 24
FAKE_SLACK = "xoxb-" + "1234567890-" + "x" * 24
FAKE_GOOGLE = "AIza" + "x" * 35
FAKE_JWT = "eyJ" + "a" * 20 + "." + "b" * 30 + "." + "c" * 40
FAKE_PEM = "-----BEGIN RSA PRIVATE KEY-----\nMIIEfakefakefake\nfakefake==\n-----END RSA PRIVATE KEY-----"  # security-review: ignore - synthetic redaction fixture
FAKE_HEX40 = "a" * 40


def _assert_gone(out: str, value: str) -> None:
    assert value not in out
    assert "<redacted:" in out


class TestVendorTokens:
    @pytest.mark.parametrize(
        ("value", "kind"),
        [
            (FAKE_AWS, "aws-key"),
            (FAKE_ASIA, "aws-key"),
            (FAKE_GHP, "github"),
            (FAKE_GHO, "github"),
            (FAKE_OPENAI, "openai"),
            (FAKE_STRIPE, "stripe"),
            (FAKE_STRIPE_TEST, "stripe"),
            (FAKE_SLACK, "slack"),
            (FAKE_GOOGLE, "google"),
            (FAKE_JWT, "jwt"),
        ],
    )
    def test_redacts_each_vendor_format(self, value: str, kind: str) -> None:
        out, types = jev_redact.redact_text(f"value is {value} end")
        _assert_gone(out, value)
        assert types == [kind]
        assert f"<redacted:{kind}:{value[-4:]}>" in out

    def test_pem_block_replaced_whole(self) -> None:
        out, types = jev_redact.redact_text(f"cat key\n{FAKE_PEM}\ndone")
        assert "PRIVATE KEY" not in out
        assert "MIIEfake" not in out
        assert types == ["pem"]
        assert out == "cat key\n<redacted:pem:---->\ndone"


class TestHeaders:
    def test_bearer(self) -> None:
        out, types = jev_redact.redact_text("Authorization: Bearer " + "t" * 30)
        assert "t" * 30 not in out
        assert "bearer" in types

    def test_authorization_basic(self) -> None:
        out, types = jev_redact.redact_text("Authorization: Basic " + "QUJD" * 6)
        assert "QUJD" * 6 not in out
        assert types == ["authorization"]

    def test_cookie_and_set_cookie(self) -> None:
        text = "Cookie: session=abcdefghijklmnop; other=1\nSet-Cookie: sid=zyxwvutsrqponm; Path=/"
        out, types = jev_redact.redact_text(text)
        assert "abcdefghijklmnop" not in out
        assert "zyxwvutsrqponm" not in out
        assert types == ["cookie", "cookie"]


class TestKeyValue:
    @pytest.mark.parametrize(
        "text",
        [
            "API_KEY=supersecretvalue123",
            "api-key: supersecretvalue123",
            '"password": "supersecretvalue123"',
            "DB_PASSWORD='supersecretvalue123'",  # security-review: ignore - synthetic redaction fixture
            "private_token=supersecretvalue123",
            "credential = supersecretvalue123",
            "auth_secret=supersecretvalue123",
        ],
    )
    def test_kv_forms(self, text: str) -> None:
        out, types = jev_redact.redact_text(text)
        assert "supersecretvalue123" not in out
        assert types == ["kv"]
        assert out.endswith("<redacted:kv:e123>") or out.endswith("<redacted:kv:e123>'") or "<redacted:kv:e123>" in out

    def test_short_value_no_last4(self) -> None:
        out, types = jev_redact.redact_text("token=abcdefgh")
        assert out == "token=<redacted:kv>"
        assert types == ["kv"]

    def test_value_under_8_chars_untouched(self) -> None:
        out, types = jev_redact.redact_text("token=abc")
        assert out == "token=abc"
        assert types == []

    def test_url_credentials(self) -> None:
        out, types = jev_redact.redact_text("postgres://user:hunter2hunter2@db.internal:5432/app")
        assert "hunter2hunter2" not in out
        assert "user:" in out
        assert "@db.internal" in out
        assert types == ["url-cred"]

    def test_entropy_next_to_key_name(self) -> None:
        blob = "A" * 44
        out, types = jev_redact.redact_text(f"aws_secret_access_key -> {blob}")
        assert blob not in out
        assert types == ["entropy"]

    def test_aws_secret_key_pair(self) -> None:
        secret = "w" * 40  # security-review: ignore - synthetic redaction fixture
        text = f"aws_access_key_id = {FAKE_AWS}\naws_secret_access_key = {secret}"
        out, types = jev_redact.redact_text(text)
        assert FAKE_AWS not in out
        assert secret not in out
        assert sorted(types) == ["aws-key", "kv"]


class TestNegativeCases:
    @pytest.mark.parametrize(
        "text",
        [
            "id = 123e4567-e89b-12d3-a456-426614174000",
            f"commit {FAKE_HEX40} (HEAD -> main)",
            "src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4'",
            "def authenticate(user): return user.is_active",
            "author = 'Alice'",
            "the task-list is long and the desk-lamp is on",
            "SELECT * FROM tokens WHERE id = 1",
        ],
    )
    def test_untouched(self, text: str) -> None:
        out, types = jev_redact.redact_text(text)
        assert out == text
        assert types == []

    def test_empty_and_non_string(self) -> None:
        assert jev_redact.redact_text("") == ("", [])
        assert jev_redact.redact_text(None) == (None, [])  # type: ignore[arg-type]


class TestRedactPayload:
    def test_walks_state_and_questions(self) -> None:
        payload = {
            "model": "jev-latest",
            "state": {
                "text": f"export GITHUB_TOKEN={FAKE_GHP}",
                "history": [{"role": "user", "text": f"use {FAKE_AWS}"}, {"n": 3}],
                "nested": {"deep": [f"{FAKE_OPENAI}"]},
            },
            "questions": [
                {"id": "q1", "instructions": f"is {FAKE_JWT} valid", "criteria": ["clean", FAKE_SLACK]},
                {"id": "q2", "instructions": "no secrets here"},
            ],
        }
        original = repr(payload)
        out, n = jev_redact.redact_payload(payload)
        assert n == 5
        assert repr(payload) == original  # input untouched (deep copy)
        dumped = repr(out)
        for fake in (FAKE_GHP, FAKE_AWS, FAKE_OPENAI, FAKE_JWT, FAKE_SLACK):
            assert fake not in dumped
        assert out["model"] == "jev-latest"
        assert out["state"]["history"][1] == {"n": 3}
        assert out["questions"][1]["instructions"] == "no secrets here"

    def test_walks_dict_shaped_question_instructions_and_criteria(self) -> None:
        payload = {
            "state": {"safe": True},
            "questions": {
                "first": {
                    "type": "noul",
                    "instructions": f"classify token={FAKE_GHP}",
                    "criteria": {"yes": f"contains {FAKE_OPENAI}"},
                },
                "second": {"type": "noul", "instructions": "no secrets"},
            },
        }

        out, n = jev_redact.redact_payload(payload)

        assert n == 2
        dumped = repr(out)
        assert FAKE_GHP not in dumped
        assert FAKE_OPENAI not in dumped
        assert FAKE_GHP in repr(payload)

    def test_clean_payload_count_zero(self) -> None:
        payload = {"state": {"text": "hello world"}, "questions": [{"id": "q", "instructions": "ok"}]}
        out, n = jev_redact.redact_payload(payload)
        assert n == 0
        assert out == payload


class TestProtectedPath:
    @pytest.mark.parametrize(
        "path",
        [
            "/home/u/project/.env",
            "/home/u/project/.env.local",
            "certs/server.pem",
            "certs/server.key",
            "/home/u/.ssh/id_ed25519",
            "id_rsa",
            "token.json",
            ".tokens",
            "client.p12",
            "client.pfx",
            "credentials.json",
            "credentials",
            "service-account-prod.json",
            "/home/u/.gnupg/pubring.kbx",
            "/home/u/.aws/config",
            "/home/u/.config/gh/hosts.yml",
            "deploy/secrets/db.yaml",
            "keyring",
            "/var/lib/keyring/x",
        ],
    )
    def test_protected(self, path: str) -> None:
        assert jev_redact.is_protected_path(path) is True
        assert jev_redact.is_protected_path(Path(path)) is True

    @pytest.mark.parametrize(
        "path",
        [
            "/home/u/project/main.py",
            "README.md",
            "environment.yml",
            "docs/identity.md",
            "src/keys.py",
            "service-account.md",
            "tests/test_env.py",
        ],
    )
    def test_not_protected(self, path: str) -> None:
        assert jev_redact.is_protected_path(path) is False
