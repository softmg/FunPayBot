from unittest.mock import patch

import bot.credential_confirmations as cc
from bot.credential_confirmations import create_pending_credentials, pop_pending_credentials


def setup_function() -> None:
    cc._pending_credentials.clear()


def test_create_then_pop_returns_pending() -> None:
    token = create_pending_credentials(1, "user@example.com:pw", "chat-uuid")
    pending = pop_pending_credentials(token)
    assert pending is not None
    assert pending.manager_telegram_id == 1
    assert pending.credentials == "user@example.com:pw"
    assert pending.chat_id == "chat-uuid"


def test_pop_unknown_token_returns_none() -> None:
    assert pop_pending_credentials("missing") is None


def test_pop_is_single_use() -> None:
    token = create_pending_credentials(1, "creds", None)
    assert pop_pending_credentials(token) is not None
    assert pop_pending_credentials(token) is None


def test_expired_entries_are_not_returned() -> None:
    with patch("bot.credential_confirmations.time.monotonic", return_value=0.0):
        token = create_pending_credentials(1, "creds", None)
    with patch("bot.credential_confirmations.time.monotonic", return_value=cc.PENDING_TTL_SECONDS + 1):
        assert pop_pending_credentials(token) is None


def test_store_is_capped_evicting_oldest(monkeypatch) -> None:
    monkeypatch.setattr(cc, "MAX_PENDING", 2)
    first = create_pending_credentials(1, "a", None)
    create_pending_credentials(2, "b", None)
    create_pending_credentials(3, "c", None)

    assert len(cc._pending_credentials) == 2
    # The oldest token was evicted when the third entry pushed past the cap.
    assert pop_pending_credentials(first) is None
