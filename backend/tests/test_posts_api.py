from app import create_app
from app.extensions import db
from app.models import Calendar, CalendarSource, Post, PostType


def setup_test_db(app):
    with app.app_context():
        db.create_all()


def _create_user(client, email="posts@example.com", password="password123"):
    return client.post(
        "/api/auth/signup",
        json={"email": email, "password": password},
    )


def test_sync_posts_endpoint_calls_sync_and_returns_summary(monkeypatch):
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup_response = _create_user(client)
    assert signup_response.status_code == 201

    with app.app_context():
        user_id = signup_response.get_json()["user"]["id"]

        calendar = Calendar(
            user_id=user_id,
            name="GetLate Team",
            source=CalendarSource.GETLATE,
            source_profile_id="profile_123",
        )
        calendar.set_api_key("secret-key")
        db.session.add(calendar)
        db.session.commit()

    class FakeResult:
        fetched = 5
        created = 4
        updated = 1

    def fake_sync(calendar):
        assert calendar.name == "GetLate Team"
        return FakeResult()

    monkeypatch.setattr("app.routes.sync_calendar_posts", fake_sync)

    response = client.post("/api/posts/sync", json={})
    assert response.status_code == 200

    payload = response.get_json()
    assert len(payload["results"]) == 1
    assert payload["results"][0]["fetched"] == 5
    assert payload["results"][0]["created"] == 4
    assert payload["results"][0]["updated"] == 1


def test_list_posts_returns_only_logged_in_users_posts():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup_response = _create_user(client)
    assert signup_response.status_code == 201

    user_id = signup_response.get_json()["user"]["id"]

    with app.app_context():
        post_type = PostType(name="General", slug="general")
        db.session.add(post_type)
        db.session.flush()

        calendar = Calendar(
            user_id=user_id,
            name="Main",
            source=CalendarSource.GETLATE,
            source_profile_id="profile_123",
        )
        calendar.set_api_key("secret-key")
        db.session.add(calendar)
        db.session.flush()

        post = Post(
            calendar_id=calendar.id,
            post_type_id=post_type.id,
            external_id="ext_1",
            title="Scheduled Post",
            status="scheduled",
        )
        db.session.add(post)
        db.session.commit()

    response = client.get("/api/posts")
    assert response.status_code == 200

    payload = response.get_json()
    assert len(payload["posts"]) == 1
    assert payload["posts"][0]["title"] == "Scheduled Post"
    assert payload["posts"][0]["calendar_id"] is not None
