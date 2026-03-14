from app import create_app
from app.extensions import db
from app.models import Calendar, CalendarSource, Post, PostType, User


def test_calendar_post_schema_relationships():
    app = create_app("testing")

    with app.app_context():
        db.create_all()

        user = User(email="owner@example.com", password_hash="hashed-value")
        post_type = PostType(name="Blog", slug="blog", description="Blog article")
        calendar = Calendar(
            user_id=1,
            name="GetLate Main",
            source=CalendarSource.GETLATE,
            external_id="cal_123",
        )

        db.session.add(user)
        db.session.flush()

        calendar.user_id = user.id
        db.session.add(post_type)
        db.session.add(calendar)
        db.session.flush()

        post = Post(
            calendar_id=calendar.id,
            post_type_id=post_type.id,
            title="Upcoming launch post",
            status="scheduled",
        )
        db.session.add(post)
        db.session.commit()

        saved_calendar = db.session.get(Calendar, calendar.id)
        saved_post = db.session.get(Post, post.id)

        assert saved_calendar is not None
        assert saved_calendar.source == CalendarSource.GETLATE
        assert saved_calendar.owner.email == "owner@example.com"
        assert len(saved_calendar.posts) == 1

        assert saved_post is not None
        assert saved_post.calendar.name == "GetLate Main"
        assert saved_post.post_type.slug == "blog"
