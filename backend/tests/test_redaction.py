import pytest

from app.core.redaction import redact_secret, redact_text


@pytest.mark.parametrize(
    ("secret", "expected"),
    [
        ("", "****"),
        ("12345678", "****"),
        ("123456789", "12****89"),
        ("1234567890123456", "12****56"),
        ("12345678901234567", "1234****4567"),
    ],
)
def test_redact_secret_follows_length_tiers(secret: str, expected: str) -> None:
    assert redact_secret(secret) == expected


def test_redact_text_masks_sk_keys() -> None:
    assert redact_text("key sk-live-abcdefghijklmnop leaked") == "key sk-l****mnop leaked"


def test_redact_text_masks_bearer_tokens() -> None:
    assert redact_text("Authorization: Bearer abcdefghijklmnopqrst") == (
        "Authorization: Bearer abcd****qrst"
    )


def test_redact_text_masks_api_key_assignments() -> None:
    assert redact_text("api_key=abcdefgh12345678") == "api_key=ab****78"
    assert redact_text("api_key='short'") == "api_key='****'"


def test_redact_text_leaves_plain_text_unchanged() -> None:
    assert redact_text("backend: ok") == "backend: ok"
