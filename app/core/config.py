from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str = "postgresql://postgres:kIimQyHyhFaHjjXdLaWmLNFhifRxuwWR@postgres.railway.internal:5432/railway"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "*"
    debug: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
