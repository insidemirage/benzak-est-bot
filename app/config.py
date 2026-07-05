from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    all_proxy: Optional[str] = Field(default=None, alias="ALL_PROXY")
    database_path: str = Field(default="data/bot.sqlite3", alias="DATABASE_PATH")
    check_throttle_seconds: int = Field(default=30, alias="CHECK_THROTTLE_SECONDS")
    dev_mode: bool = Field(default=False, alias="DEV_MODE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    admin_id: Optional[int] = Field(default=None, alias="ADMIN_ID")

    @field_validator("admin_id", mode="before")
    @classmethod
    def empty_admin_id_is_none(cls, value):
        if value == "":
            return None

        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
