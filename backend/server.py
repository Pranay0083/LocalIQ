"""ASGI entry point: `uvicorn server:app --port 8001`. The application lives in app/main.py."""
from app.main import app  # noqa: F401
