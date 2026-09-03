from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# pydantic-settings' `env_file` loading only populates the Settings object
# below — it does NOT export those values into os.environ. Several modules
# in this codebase (app/services/sentiment_service.py) read GROQ_API_KEY via
# os.getenv() directly, so without this explicit load_dotenv() call, that
# lookup silently returns None even when .env has a valid key, and the
# sentiment pipeline silently falls back to neutral defaults for every post.
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "SIH Social Media Intelligence"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/sih_db"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "qwen/qwen3.6-27b"
    REDIS_URL: str = "redis://localhost:6379/0"
    API_V1_STR: str = "/api/v1"
    X_BEARER_TOKEN: str = ""
    X_DEMO_FALLBACK: bool = True
    # Comma-separated list of allowed frontend origins, e.g.
    # "https://civicshield.vercel.app,http://localhost:5173"
    # Defaults to "*" (open) for easy local/hackathon dev; set this explicitly
    # once you have a deployed frontend URL.
    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()