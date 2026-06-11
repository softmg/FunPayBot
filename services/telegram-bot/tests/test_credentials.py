from bot.credentials import extract_credentials


def test_extract_credentials_from_email_pair() -> None:
    assert extract_credentials("take it user@example.com:pa55word") == "user@example.com:pa55word"


def test_extract_credentials_from_labeled_message() -> None:
    assert extract_credentials("Логин: buyer123\nПароль: secret456") == "buyer123:secret456"


def test_extract_credentials_from_funpay_code_site_message() -> None:
    message = (
        "САЙТ С КОДОМ: http://45.63.9.253:8080/\n"
        "ввести: siptqrmuw86489+4913fda6@outlook.com----#C#QrNA6jd7r$eFd"
    )

    assert extract_credentials(message) == "siptqrmuw86489+4913fda6@outlook.com:#C#QrNA6jd7r$eFd"


def test_extract_credentials_returns_none_for_plain_text() -> None:
    assert extract_credentials("hello, when can you deliver?") is None


def test_extract_credentials_ignores_email_mentioned_in_a_sentence() -> None:
    # A bare space after an email is not a credential delimiter.
    assert extract_credentials("write to user@mail.com today please") is None
    assert extract_credentials("контакт support@shop.com спасибо") is None


def test_extract_credentials_accepts_explicit_delimiters() -> None:
    assert extract_credentials("user@example.com | secretpw") == "user@example.com:secretpw"
    assert extract_credentials("user@example.com/secretpw") == "user@example.com:secretpw"
