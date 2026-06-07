from enum import Enum
from typing import Any


def enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def message_to_dict(message: Any) -> dict:
    return {
        "id": getattr(message, "id", None),
        "chat_id": getattr(message, "chat_id", None),
        "chat_name": getattr(message, "chat_name", None),
        "interlocutor_id": getattr(message, "interlocutor_id", None),
        "author": getattr(message, "author", None),
        "author_id": getattr(message, "author_id", None),
        "text": getattr(message, "text", None),
        "image_link": getattr(message, "image_link", None),
        "image_name": getattr(message, "image_name", None),
        "badge": getattr(message, "badge", None),
        "type": enum_value(getattr(message, "type", None)),
        "by_bot": getattr(message, "by_bot", False),
        "by_vertex": getattr(message, "by_vertex", False),
    }


def chat_shortcut_to_dict(chat: Any) -> dict:
    return {
        "id": getattr(chat, "id", None),
        "name": getattr(chat, "name", None),
        "last_message_text": getattr(chat, "last_message_text", None),
        "last_by_bot": getattr(chat, "last_by_bot", None),
        "last_by_vertex": getattr(chat, "last_by_vertex", None),
        "unread": getattr(chat, "unread", None),
        "node_msg_id": getattr(chat, "node_msg_id", None),
        "user_msg_id": getattr(chat, "user_msg_id", None),
        "last_message_type": enum_value(getattr(chat, "last_message_type", None)),
    }


def chat_to_dict(chat: Any) -> dict:
    return {
        "id": getattr(chat, "id", None),
        "name": getattr(chat, "name", None),
        "looking_link": getattr(chat, "looking_link", None),
        "looking_text": getattr(chat, "looking_text", None),
        "messages": [message_to_dict(message) for message in getattr(chat, "messages", [])],
    }


def order_to_dict(order: Any) -> dict:
    return {
        "id": getattr(order, "id", None),
        "status": enum_value(getattr(order, "status", None)),
        "sum": getattr(order, "sum", None),
        "currency": enum_value(getattr(order, "currency", None)),
        "amount": getattr(order, "amount", None),
        "buyer_id": getattr(order, "buyer_id", None),
        "buyer_username": getattr(order, "buyer_username", None),
        "seller_id": getattr(order, "seller_id", None),
        "seller_username": getattr(order, "seller_username", None),
        "chat_id": getattr(order, "chat_id", None),
        "player": getattr(order, "player", None),
        "order_secrets": getattr(order, "order_secrets", []),
        "fields": {
            key: {
                "name": getattr(field, "name", None),
                "value": getattr(field, "value", None),
            }
            for key, field in getattr(order, "fields", {}).items()
        },
    }

