from datetime import UTC, datetime
import traceback

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import Calendar, CalendarSource, Post, User
from .post_ingestion import sync_calendar_posts


api_bp = Blueprint("api", __name__)


def serialize_calendar(calendar: Calendar) -> dict:
    return {
        "id": calendar.id,
        "name": calendar.name,
        "source": calendar.source.value,
        "source_profile_id": calendar.source_profile_id,
        "source_profile_name": calendar.source_profile_name,
        "external_id": calendar.external_id,
        "is_active": calendar.is_active,
        "created_at": calendar.created_at.isoformat() if calendar.created_at else None,
        "updated_at": calendar.updated_at.isoformat() if calendar.updated_at else None,
    }


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


@api_bp.post("/calendars")
@login_required
def create_calendar():
    payload = request.get_json(silent=True) or {}

    source_raw = (payload.get("source") or "").strip().lower()
    api_key = (payload.get("api_key") or "").strip()
    provided_name = (payload.get("name") or "").strip()
    profile_id = (payload.get("profile_id") or "").strip()
    profile_name = (payload.get("profile_name") or "").strip() or None

    try:
        source = CalendarSource(source_raw)
    except ValueError:
        return jsonify({"error": "Invalid source"}), 400

    if source == CalendarSource.GETLATE:
        if not api_key:
            return jsonify({"error": "GetLate requires api_key"}), 400
        if not profile_id:
            return jsonify({"error": "GetLate requires profile_id"}), 400

        existing = db.session.execute(
            db.select(Calendar).filter_by(
                user_id=current_user.id,
                source=CalendarSource.GETLATE,
                source_profile_id=profile_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return jsonify({"error": "Calendar for this GetLate profile already exists"}), 409

        calendar_name = provided_name or f"GetLate - {profile_name or profile_id}"
        calendar = Calendar(
            user_id=current_user.id,
            name=calendar_name,
            source=source,
            source_profile_id=profile_id,
            source_profile_name=profile_name,
            external_id=profile_id,
            is_active=True,
        )
        calendar.set_api_key(api_key)
    elif source == CalendarSource.GHOST_BLOG:
        if not api_key:
            return jsonify({"error": "Ghost Blog requires api_key"}), 400

        calendar_name = provided_name or "Ghost Blog"
        calendar = Calendar(
            user_id=current_user.id,
            name=calendar_name,
            source=source,
            source_profile_id=None,
            source_profile_name=None,
            is_active=True,
        )
        calendar.set_api_key(api_key)
    else:
        return jsonify({"error": "Source not supported yet"}), 400

    db.session.add(calendar)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "Calendar created",
                "calendar": serialize_calendar(calendar),
            }
        ),
        201,
    )


@api_bp.get("/calendars")
@login_required
def list_calendars():
    calendars = db.session.execute(
        db.select(Calendar)
        .filter_by(user_id=current_user.id)
        .order_by(Calendar.created_at.desc())
    ).scalars()

    return jsonify({"calendars": [serialize_calendar(calendar) for calendar in calendars]})


def serialize_post(post):
    return {
        "id": post.id,
        "calendar_id": post.calendar_id,
        "title": post.title,
        "status": post.status,
        "scheduled_for": post.scheduled_for.isoformat() if post.scheduled_for else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
    }


@api_bp.route("/posts/sync", methods=["POST"])
@login_required
def sync_posts():
    payload = request.get_json(silent=True) or {}
    calendar_id = payload.get("calendar_id")
    debug_enabled = bool(payload.get("debug")) or request.args.get("debug") == "1"

    query = db.select(Calendar).filter_by(user_id=current_user.id)
    if calendar_id is not None:
        query = query.filter_by(id=calendar_id)

    calendars = db.session.execute(query.order_by(Calendar.id.asc())).scalars().all()
    if not calendars:
        return jsonify({"message": "No calendars found", "results": []}), 200

    results = []
    for calendar in calendars:
        try:
            summary = sync_calendar_posts(calendar)

            db_post_count = db.session.execute(
                db.select(db.func.count(Post.id)).filter(Post.calendar_id == calendar.id)
            ).scalar_one()

            results.append(
                {
                    "calendar_id": calendar.id,
                    "calendar_name": calendar.name,
                    "source": calendar.source.value,
                    "fetched": summary.fetched,
                    "created": summary.created,
                    "updated": summary.updated,
                    "db_post_count": db_post_count,
                }
            )
        except Exception as exc:
            current_trace = traceback.format_exc() if debug_enabled else None
            results.append(
                {
                    "calendar_id": calendar.id,
                    "calendar_name": calendar.name,
                    "source": calendar.source.value,
                    "error": str(exc),
                    "debug_trace": current_trace,
                }
            )

    return jsonify({"results": results, "debug": debug_enabled})


@api_bp.route("/posts", methods=["GET"])
@login_required
def list_posts():
    calendar_id = request.args.get("calendar_id", type=int)

    query = (
        db.select(Post)
        .join(Calendar, Post.calendar_id == Calendar.id)
        .filter(Calendar.user_id == current_user.id)
    )

    if calendar_id is not None:
        query = query.filter(Calendar.id == calendar_id)

    posts = db.session.execute(
        query.order_by(Post.scheduled_for.asc().nulls_last(), Post.id.asc())
    ).scalars().all()

    return jsonify({"posts": [serialize_post(post) for post in posts]})
