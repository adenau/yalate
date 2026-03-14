from datetime import UTC, datetime
from enum import Enum

from flask import current_app
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .security import encrypt_secret, maybe_decrypt_secret


class CalendarSource(str, Enum):
    GETLATE = "getlate"
    GHOST_BLOG = "ghost_blog"
    WORDPRESS = "wordpress"


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
    calendars = db.relationship(
        "Calendar",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy=True,
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


class Calendar(db.Model):
    __tablename__ = "calendars"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    source = db.Column(
        db.Enum(CalendarSource, native_enum=False, length=32),
        nullable=False,
        default=CalendarSource.GETLATE,
    )
    api_key = db.Column(db.String(255), nullable=True)
    source_profile_id = db.Column(db.String(128), nullable=True, index=True)
    source_profile_name = db.Column(db.String(120), nullable=True)
    external_id = db.Column(db.String(128), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    owner = db.relationship("User", back_populates="calendars", lazy=True)
    posts = db.relationship(
        "Post",
        back_populates="calendar",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def set_api_key(self, raw_api_key: str) -> None:
        encryption_key = current_app.config["CALENDAR_KEYS_ENCRYPTION_KEY"]
        self.api_key = encrypt_secret(raw_api_key, encryption_key)

    def get_api_key(self) -> str | None:
        if not self.api_key:
            return None

        encryption_key = current_app.config["CALENDAR_KEYS_ENCRYPTION_KEY"]
        return maybe_decrypt_secret(self.api_key, encryption_key)


class PostType(db.Model):
    __tablename__ = "post_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    slug = db.Column(db.String(64), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    posts = db.relationship("Post", back_populates="post_type", lazy=True)


class Post(db.Model):
    __tablename__ = "posts"
    __table_args__ = (
        db.UniqueConstraint("calendar_id", "external_id", name="uq_posts_calendar_external"),
    )

    id = db.Column(db.Integer, primary_key=True)
    calendar_id = db.Column(
        db.Integer,
        db.ForeignKey("calendars.id"),
        nullable=False,
        index=True,
    )
    post_type_id = db.Column(
        db.Integer,
        db.ForeignKey("post_types.id"),
        nullable=True,
        index=True,
    )
    external_id = db.Column(db.String(128), nullable=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="scheduled")
    scheduled_for = db.Column(db.DateTime(timezone=True), nullable=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    calendar = db.relationship("Calendar", back_populates="posts", lazy=True)
    post_type = db.relationship("PostType", back_populates="posts", lazy=True)
