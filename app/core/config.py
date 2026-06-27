from pydantic_settings import BaseSettings, SettingsConfigDict

# All frontend origins that should be allowed.
# In production the CORS_ORIGINS env-var is set in the Railway dashboard.
# This default covers the known Railway frontend URL + local development.
_DEFAULT_CORS_ORIGINS = ",".join([
    "https://mmb-frontend-production-f434.up.railway.app",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:4173",
])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str = "postgresql://postgres:SENHA@postgres.railway.internal:5432/railway"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = _DEFAULT_CORS_ORIGINS
    debug: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
