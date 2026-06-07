from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    admin_telegram_ids: str = ""
    database_url: str = "postgresql://funpaybot:funpaybot@db:5432/funpaybot"
    funpay_api_url: str = "http://funpay-api:8000"
    funpay_poll_interval_seconds: int = 20
    @property
    def admin_ids(self) -> set[int]:
        return {
            int(value.strip())
            for value in self.admin_telegram_ids.split(",")
            if value.strip().isdigit()
        }


settings = Settings()

