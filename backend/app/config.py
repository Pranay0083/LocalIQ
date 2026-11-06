import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings:
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    cors_origins = os.environ.get("CORS_ORIGINS", "*")

    jwt_secret = os.environ["JWT_SECRET"]
    admin_email = os.environ["ADMIN_EMAIL"]
    admin_password = os.environ["ADMIN_PASSWORD"]

    # 'groq' (default) or 'openai' - any OpenAI-compatible API: OpenAI, Gemini, OpenRouter, Ollama.
    llm_provider = os.environ.get("LLM_PROVIDER", "groq")
    research_provider = os.environ.get("RESEARCH_PROVIDER", "auto")

    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    groq_model_fast = os.environ.get("GROQ_MODEL_FAST", "openai/gpt-oss-20b")
    groq_model_smart = os.environ.get("GROQ_MODEL_SMART", "openai/gpt-oss-120b")
    model_search = os.environ.get("GROQ_SEARCH_MODEL", "openai/gpt-oss-20b")

    openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    openai_model_fast = os.environ.get("OPENAI_MODEL_FAST", "gpt-5.4-mini")
    openai_model_smart = os.environ.get("OPENAI_MODEL_SMART", openai_model_fast)

    # The model ids the agents ask for, resolved for the active provider.
    model_fast = openai_model_fast if llm_provider == "openai" else groq_model_fast
    model_smart = openai_model_smart if llm_provider == "openai" else groq_model_smart
    research_model = os.environ.get("RESEARCH_MODEL") or model_fast

    openweather_key = os.environ["OPENWEATHER_API_KEY"]
    overpass_url = os.environ["OVERPASS_URL"]

    razorpay_key_id = os.environ["RAZORPAY_KEY_ID"]
    razorpay_key_secret = os.environ["RAZORPAY_KEY_SECRET"]
    razorpay_webhook_secret = os.environ["RAZORPAY_WEBHOOK_SECRET"]

    free_report_limit = int(os.environ["FREE_REPORT_LIMIT"])
    search_budget = int(os.environ["SEARCH_BUDGET_PER_DOSSIER"])


settings = Settings()
