from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reads values from the .env file (or from real environment variables
    when deployed on Render)."""

    db_host: str
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str
    db_password: str

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
