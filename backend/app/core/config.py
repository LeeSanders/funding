from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Funding Backend"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./backend/funding.db"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 20
    model_config = SettingsConfigDict(env_prefix="FUNDING_", env_file=".env", extra="ignore")


settings = Settings()
