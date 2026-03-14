from app import create_app
from app.extensions import db
from app.models import Calendar


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
    assert response.get_json()["error"] == "GetLate requires profile_id"


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
    assert calendar["name"] == "GetLate - Main Brand"

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
            "name": "Ghost Editorial",
        },
    )

    assert response.status_code == 201
    calendar = response.get_json()["calendar"]
    assert calendar["source"] == "ghost_blog"
    assert calendar["name"] == "Ghost Editorial"


def test_list_calendars_requires_authentication():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    response = client.get("/api/calendars")

    assert response.status_code == 401
