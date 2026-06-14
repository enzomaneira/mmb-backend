from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str = "postgresql://brinquedos:brinquedos@localhost:5432/brinquedos_da_mae"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    debug: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
