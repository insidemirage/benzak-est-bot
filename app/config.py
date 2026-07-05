from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    all_proxy: str | None = Field(default=None, alias="ALL_PROXY")
    no_proxy: str | None = Field(default=None, alias="NO_PROXY")
    database_path: str = Field(default="data/bot.sqlite3", alias="DATABASE_PATH")
    check_throttle_seconds: int = Field(default=30, alias="CHECK_THROTTLE_SECONDS")
    dev_mode: bool = Field(default=False, alias="DEV_MODE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
