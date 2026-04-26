import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root:1234@localhost:3306/bh_service_desk?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 Mo
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "doc", "docx", "xlsx", "txt"}
    AI_SIMILARITY_ENABLED = os.environ.get("AI_SIMILARITY_ENABLED", "true").lower() == "true"
    AI_SIMILARITY_MIN_SCORE = float(os.environ.get("AI_SIMILARITY_MIN_SCORE", "0.30"))
    AI_SIMILARITY_SAME_CATEGORY_ONLY = os.environ.get("AI_SIMILARITY_SAME_CATEGORY_ONLY", "true").lower() == "true"
    AI_MAX_CORPUS_TICKETS = int(os.environ.get("AI_MAX_CORPUS_TICKETS", "500"))
