import os

from .security import derive_fernet_key


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    CALENDAR_KEYS_ENCRYPTION_KEY = os.getenv(
        "CALENDAR_KEYS_ENCRYPTION_KEY",
        derive_fernet_key(SECRET_KEY),
    )
    GETLATE_API_BASE_URL = os.getenv("GETLATE_API_BASE_URL", "https://getlate.dev/api/v1")
    GHOST_API_BASE_URL = os.getenv("GHOST_API_BASE_URL")
    CALENDAR_VALIDATE_ON_CREATE = _env_flag("CALENDAR_VALIDATE_ON_CREATE", "true")
    CALENDAR_VALIDATE_ON_UPDATE = _env_flag("CALENDAR_VALIDATE_ON_UPDATE", "true")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///yalate.db")


class ProductionConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://user:password@localhost:3306/yalate",
    )


class TestingConfig(BaseConfig):
    TESTING = True
    CALENDAR_VALIDATE_ON_CREATE = False
    CALENDAR_VALIDATE_ON_UPDATE = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
