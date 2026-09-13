import os
from dotenv import load_dotenv

load_dotenv()


class Setting:
    """
    Central configuration class.
    All secrets and tunables are loaded from environment variables (.env file).
    """

    # ── AI / LLM API Keys ──
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

    # ── Database ──
    MONGODB_URL_KEY: str = os.getenv("MONGODB_URL_KEY", "")

    # ── LLM Fallback Chain ──
    DEFAULT_MODELS: list[str] = [
        "mistral/mistral-small-latest",
        "mistral/mistral-large-latest",
        "deepseek/deepseek-chat",
        "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
    ]
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0

    # ── JWT Token Configuration ──
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # ── Clerk Auth ──
    CLERK_PUBLISHABLE_KEY: str = os.getenv("CLERK_PUBLISHABLE_KEY", "")
    CLERK_SECRET_KEY: str = os.getenv("CLERK_SECRET_KEY", "").strip()
    CLERK_ISSUER: str = (os.getenv("CLERK_ISSUER", "").strip() or "https://coherent-eel-9638.clerk.accounts.dev")

    # ── Google OAuth 2.0 (MCP & Calendar Integration) ──
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8010/api/auth/google/callback")


# Convenience alias
Setting.setting = Setting

