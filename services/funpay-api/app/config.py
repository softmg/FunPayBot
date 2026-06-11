from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    funpay_base_url: str = "https://funpay.com"
    funpay_category_path: str = "lots/1355/"
    funpay_golden_key: str = ""
    funpay_user_agent: str | None = None
    funpay_max_actions_per_minute: int = 100
    # Shared secret required on every request (except /health). When empty the
    # API is unprotected; this is logged loudly at startup.
    internal_api_token: str = ""


settings = Settings()
