from bot.config import Settings


def test_internal_headers_empty_when_token_unset() -> None:
    settings = Settings(internal_api_token="")
    assert settings.internal_headers() == {}


def test_internal_headers_set_when_token_present() -> None:
    settings = Settings(internal_api_token="s3cret")
    assert settings.internal_headers() == {"X-Internal-Token": "s3cret"}


def test_admin_ids_parses_comma_separated_digits() -> None:
    settings = Settings(admin_telegram_ids="1, 2 ,abc,3")
    assert settings.admin_ids == {1, 2, 3}
