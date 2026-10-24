"""Reads settings from the .env file (locally) or from environment
variables (on Render). Nothing secret is written in the code."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database: Supabase -> Connect -> Session pooler
    db_host: str
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str
    db_password: str

    # Supabase login service
    supabase_url: str
    supabase_key: str      # the PUBLISHABLE (anon) key. Never the secret key.
    admin_email: str       # the only email allowed to log in

    # Login cookie signing
    session_secret: str
    app_env: str = "development"   # set to "production" on Render

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
