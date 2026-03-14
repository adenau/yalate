from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import User


api_bp = Blueprint("api", __name__)


@api_bp.get("/hello")
def hello_world():
    return jsonify({"message": "Hello from YaLate backend!"})


@api_bp.post("/auth/signup")
def signup():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    display_name = (payload.get("display_name") or "").strip() or None

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    existing_user = db.session.execute(
        db.select(User).filter_by(email=email)
    ).scalar_one_or_none()
    if existing_user is not None:
        return jsonify({"error": "Email already in use"}), 409

    new_user = User(email=email, display_name=display_name)
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    login_user(new_user)

    return (
        jsonify(
            {
                "message": "Signup successful",
                "user": {
                    "id": new_user.id,
                    "email": new_user.email,
                    "display_name": new_user.display_name,
                },
            }
        ),
        201,
    )


@api_bp.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
    if user is None or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.is_active:
        return jsonify({"error": "User account is inactive"}), 403

    user.record_login()
    user.updated_at = datetime.now(UTC)
    db.session.commit()

    login_user(user)

    return jsonify(
        {
            "message": "Login successful",
            "user": {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "last_login": user.last_login.isoformat() if user.last_login else None,
            },
        }
    )


@api_bp.post("/auth/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logout successful"})


@api_bp.get("/auth/me")
def me():
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False, "user": None})

    return jsonify(
        {
            "authenticated": True,
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "display_name": current_user.display_name,
                "signup_date": current_user.signup_date.isoformat()
                if current_user.signup_date
                else None,
                "last_login": current_user.last_login.isoformat()
                if current_user.last_login
                else None,
            },
        }
    )
