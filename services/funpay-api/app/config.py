from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    funpay_base_url: str = "https://funpay.com"
    funpay_category_path: str = "lots/1355/"
    funpay_golden_key: str = ""
    funpay_max_actions_per_minute: int = 100


settings = Settings()

