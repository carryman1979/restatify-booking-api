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
    google_write_events_enabled: bool = True
    google_write_calendar_id: str = ""
    sync_window_days: int = 30
    sync_config_path: str = "./sync-config.json"
    conflict_notify_enabled: bool = False
    conflict_notify_email: str = ""
    conflict_notify_from: str = "restatify-booking-api@localhost"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_starttls: bool = True
    smtp_use_ssl: bool = False


settings = Settings()
