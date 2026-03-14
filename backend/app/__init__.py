import os

from flask import Flask
from flask_cors import CORS

from .config import DevelopmentConfig, ProductionConfig, TestingConfig
from .extensions import db, login_manager, migrate
from .routes import api_bp


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)

    env_name = config_name or os.getenv("FLASK_ENV", "development")
    config_mapping = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }

    app.config.from_object(config_mapping.get(env_name, DevelopmentConfig))

    CORS(app, supports_credentials=True)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from . import models

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(models.User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return {"error": "Authentication required"}, 401

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.cli.command("init-db")
    def init_db_command():
        db.create_all()
        print("Database tables created.")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
