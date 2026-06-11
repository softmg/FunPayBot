"""Tracks the most recent FunPay chat relayed to each manager.

When a manager pastes credentials directly (rather than tapping the inline
"save" button on a relayed message), we associate them with the last chat that
was relayed to that manager so the stored account keeps its chat link.
"""

_last_relay_chat: dict[int, str] = {}


def set_last_relay_chat(manager_telegram_id: int, internal_chat_id: str) -> None:
    _last_relay_chat[manager_telegram_id] = internal_chat_id


def get_last_relay_chat(manager_telegram_id: int) -> str | None:
    return _last_relay_chat.get(manager_telegram_id)
