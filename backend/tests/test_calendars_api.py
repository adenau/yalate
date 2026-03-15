from app import create_app
from app.extensions import db
from app.models import Calendar, CalendarSource


def setup_test_db(app):
    with app.app_context():
        db.create_all()


def signup(client, email="calendar.user@example.com"):
    return client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "supersecret",
        },
    )


def test_create_getlate_calendar_requires_profile_id():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup(client)

    response = client.post(
        "/api/calendars",
        json={
            "source": "getlate",
            "api_key": "sk_test_123",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Late requires profile_id"


def test_create_getlate_calendar_success():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup(client)

    response = client.post(
        "/api/calendars",
        json={
            "source": "getlate",
            "api_key": "sk_test_abc",
            "profile_id": "prof_123",
            "profile_name": "Main Brand",
        },
    )

    assert response.status_code == 201
    calendar = response.get_json()["calendar"]
    assert calendar["source"] == "getlate"
    assert calendar["source_profile_id"] == "prof_123"
    assert calendar["name"] == "Late - Main Brand"

    with app.app_context():
        saved_calendar = db.session.execute(
            db.select(Calendar).filter_by(source_profile_id="prof_123")
        ).scalar_one()
        assert saved_calendar.api_key != "sk_test_abc"
        assert saved_calendar.get_api_key() == "sk_test_abc"


def test_create_ghost_calendar_success():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup(client)

    response = client.post(
        "/api/calendars",
        json={
            "source": "ghost_blog",
            "api_key": "ghost_admin_key",
            "blog_url": "https://demo.ghost.io",
            "name": "Ghost Editorial",
        },
    )

    assert response.status_code == 201
    calendar = response.get_json()["calendar"]
    assert calendar["source"] == "ghost_blog"
    assert calendar["name"] == "Ghost Editorial"
    assert calendar["source_profile_id"] == "https://demo.ghost.io"


def test_create_ghost_calendar_requires_blog_url():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup(client)

    response = client.post(
        "/api/calendars",
        json={
            "source": "ghost_blog",
            "api_key": "ghost_admin_key",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Ghost Blog requires blog_url"


def test_list_calendars_requires_authentication():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    response = client.get("/api/calendars")

    assert response.status_code == 401


def test_validate_calendar_credentials_success(monkeypatch):
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup(client)

    def fake_validate(source, api_key, source_profile_id):
        assert source == CalendarSource.GHOST_BLOG
        assert api_key == "content_key"
        assert source_profile_id == "https://demo.ghost.io"

    monkeypatch.setattr("app.routes.validate_calendar_credentials", fake_validate)

    response = client.post(
        "/api/calendars/validate",
        json={
            "source": "ghost_blog",
            "api_key": "content_key",
            "blog_url": "https://demo.ghost.io",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["valid"] is True


def test_validate_calendar_credentials_invalid_provider_credentials(monkeypatch):
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup(client)

    def fake_validate(*_args, **_kwargs):
        raise RuntimeError("Ghost credential check failed: unauthorized (401).")

    monkeypatch.setattr("app.routes.validate_calendar_credentials", fake_validate)

    response = client.post(
        "/api/calendars/validate",
        json={
            "source": "ghost_blog",
            "api_key": "content_key",
            "blog_url": "https://demo.ghost.io",
        },
    )

    assert response.status_code == 422
    payload = response.get_json()
    assert payload["valid"] is False
    assert "unauthorized" in payload["error"]


def test_patch_calendar_updates_name_and_is_active():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup_response = signup(client)
    user_id = signup_response.get_json()["user"]["id"]

    with app.app_context():
        calendar = Calendar(
            user_id=user_id,
            name="Main",
            source=CalendarSource.GETLATE,
            source_profile_id="profile_123",
            is_active=True,
        )
        calendar.set_api_key("secret_key")
        db.session.add(calendar)
        db.session.commit()
        calendar_id = calendar.id

    response = client.patch(
        f"/api/calendars/{calendar_id}",
        json={
            "name": "Renamed",
            "is_active": False,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["calendar"]["name"] == "Renamed"
    assert payload["calendar"]["is_active"] is False


def test_delete_calendar_removes_record():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup_response = signup(client, email="delete-calendar@example.com")
    user_id = signup_response.get_json()["user"]["id"]

    with app.app_context():
        calendar = Calendar(
            user_id=user_id,
            name="Delete Me",
            source=CalendarSource.GHOST_BLOG,
            source_profile_id="https://demo.ghost.io",
            is_active=True,
        )
        calendar.set_api_key("content_key")
        db.session.add(calendar)
        db.session.commit()
        calendar_id = calendar.id

    response = client.delete(f"/api/calendars/{calendar_id}")
    assert response.status_code == 200

    with app.app_context():
        deleted = db.session.get(Calendar, calendar_id)
        assert deleted is None
