from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "production"
    host: str = "127.0.0.1"
    port: int = 8088
    api_key: str = "change-me"
    database_url: str = "sqlite+pysqlite:///./booking.db"
    default_timezone: str = "Europe/Berlin"
    workday_start_hour: int = 9
    workday_end_hour: int = 17
    slot_step_minutes: int = 30
    max_window_days: int = 30
    google_credentials_json: str = ""
    google_calendar_ids: str = ""
    sync_window_days: int = 30


settings = Settings()
