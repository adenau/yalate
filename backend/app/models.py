from datetime import UTC, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    signup_date = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
    display_name = db.Column(db.String(120), nullable=True)
    timezone = db.Column(db.String(64), nullable=False, default="UTC")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def record_login(self) -> None:
        self.last_login = datetime.now(UTC)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class ScheduledPost(db.Model):
    __tablename__ = "scheduled_posts"

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(64), nullable=False)
    external_id = db.Column(db.String(128), nullable=False)
    title = db.Column(db.String(255), nullable=False)
