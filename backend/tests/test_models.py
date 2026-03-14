from app import create_app
from app.extensions import db
from app.models import User


def test_user_model_defaults():
    app = create_app("testing")

    with app.app_context():
        db.create_all()

        user = User(email="alice@example.com", password_hash="hashed-value")
        db.session.add(user)
        db.session.commit()

        saved_user = db.session.get(User, user.id)

        assert saved_user is not None
        assert saved_user.email == "alice@example.com"
        assert saved_user.signup_date is not None
        assert saved_user.is_active is True
        assert saved_user.email_verified is False
        assert saved_user.timezone == "UTC"
