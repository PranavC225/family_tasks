import base64

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    base_url: str = "http://localhost:8000"
    secret_key: str = "dev-insecure-secret"
    database_url: str = "sqlite:///./dev.db"
    google_client_id: str = ""
    google_client_secret: str = ""
    allowed_emails: str = ""
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_subject: str = "mailto:you@example.com"

    @property
    def allowlist(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()}

    @property
    def vapid_private_key_pem(self) -> str:
        return base64.b64decode(self.vapid_private_key).decode() if self.vapid_private_key else ""

    @property
    def is_prod(self) -> bool:
        return self.env == "production"


settings = Settings()
