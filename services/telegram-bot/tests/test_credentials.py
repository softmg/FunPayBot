from bot.credentials import extract_credentials


def test_extract_credentials_from_email_pair() -> None:
    assert extract_credentials("take it user@example.com:pa55word") == "user@example.com:pa55word"


def test_extract_credentials_from_labeled_message() -> None:
    assert extract_credentials("Логин: buyer123\nПароль: secret456") == "buyer123:secret456"


def test_extract_credentials_returns_none_for_plain_text() -> None:
    assert extract_credentials("hello, when can you deliver?") is None

