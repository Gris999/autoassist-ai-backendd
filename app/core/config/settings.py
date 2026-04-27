from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AutoAssist AI Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    AI_PROVIDER: str = "gemini"
    AI_USE_FALLBACK: bool = True
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"
    OPENROUTER_TIMEOUT_SECONDS: float = 30.0
    OPENROUTER_APP_NAME: str = "AutoAssist AI Backend"
    OPENROUTER_APP_URL: str = "http://localhost:8000"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TIMEOUT_SECONDS: float = 30.0
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_TIMEOUT_SECONDS: float = 30.0
    ROBOFLOW_API_KEY: str | None = None
    ROBOFLOW_MODEL_ID: str | None = None
    ROBOFLOW_TASK_TYPE: str = "classification"
    ROBOFLOW_TIMEOUT_SECONDS: float = 30.0
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_PUBLISHABLE_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_CURRENCY: str = "usd"
    STRIPE_TIMEOUT_SECONDS: float = 30.0
    PLATFORM_COMMISSION_PERCENTAGE: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
