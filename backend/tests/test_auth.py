from app import create_app
from app.extensions import db


def setup_test_db(app):
    with app.app_context():
        db.create_all()


def test_signup_and_me_flow():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    signup_response = client.post(
        "/api/auth/signup",
        json={
            "email": "new.user@example.com",
            "password": "supersecret",
            "display_name": "New User",
        },
    )

    assert signup_response.status_code == 201
    assert signup_response.get_json()["user"]["email"] == "new.user@example.com"

    me_response = client.get("/api/auth/me")

    assert me_response.status_code == 200
    assert me_response.get_json()["authenticated"] is True
    assert me_response.get_json()["user"]["email"] == "new.user@example.com"


def test_login_logout_cycle():
    app = create_app("testing")
    setup_test_db(app)
    client = app.test_client()

    client.post(
        "/api/auth/signup",
        json={
            "email": "tester@example.com",
            "password": "supersecret",
        },
    )

    client.post("/api/auth/logout")

    login_response = client.post(
        "/api/auth/login",
        json={"email": "tester@example.com", "password": "supersecret"},
    )

    assert login_response.status_code == 200
    assert login_response.get_json()["message"] == "Login successful"

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200

    me_response = client.get("/api/auth/me")
    assert me_response.get_json()["authenticated"] is False
