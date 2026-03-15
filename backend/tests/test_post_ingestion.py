from app import create_app
import requests

from app.post_ingestion import _fetch_getlate_posts, _fetch_ghost_posts, _normalize_posts


def test_normalize_posts_uses_first_100_chars_with_line_breaks():
    raw_items = [
        {
            "id": "post_1",
            "content": "First line\nSecond line that is long enough to cross one hundred characters so trimming is required for display purposes.",
            "status": "scheduled",
        }
    ]

    normalized = _normalize_posts(raw_items)

    assert len(normalized) == 1
    preview = normalized[0]["title"]
    assert len(preview) == 100
    assert "\n" in preview
    assert preview.startswith("First line\nSecond line")


def test_normalize_posts_falls_back_to_title_when_no_content():
    raw_items = [
        {
            "id": "post_2",
            "title": "A very long title that should also be trimmed to one hundred characters if it exceeds that length by much.",
        }
    ]

    normalized = _normalize_posts(raw_items)

    assert len(normalized) == 1
    assert len(normalized[0]["title"]) == 100


def test_normalize_posts_can_prefer_title_first_for_ghost():
    raw_items = [
        {
            "id": "post_ghost_1",
            "title": "Ghost Title Wins",
            "plaintext": "This body should not replace the title when title-first is enabled.",
        }
    ]

    normalized = _normalize_posts(raw_items, prefer_title_first=True)

    assert len(normalized) == 1
    assert normalized[0]["title"] == "Ghost Title Wins"


def test_normalize_posts_marks_email_only_type():
    raw_items = [
        {
            "id": "post_email_1",
            "title": "Newsletter Only",
            "email_only": True,
            "published_at": "2026-03-14T10:00:00.000Z",
        }
    ]

    normalized = _normalize_posts(raw_items)

    assert len(normalized) == 1
    assert normalized[0]["post_type_name"] == "Email Only"


def test_normalize_posts_uses_getlate_platform_as_type():
    raw_items = [
        {
            "id": "post_social_1",
            "content": "Hello X",
            "platforms": [{"platform": "twitter", "accountId": "acc_1"}],
            "scheduledFor": "2026-03-14T11:00:00.000Z",
        }
    ]

    normalized = _normalize_posts(raw_items)

    assert len(normalized) == 1
    assert normalized[0]["post_type_name"] == "twitter"
    assert normalized[0]["external_id"] == "post_social_1::twitter"


def test_normalize_posts_splits_multi_platform_into_multiple_records():
    raw_items = [
        {
            "id": "post_social_2",
            "content": "Cross post",
            "platforms": [
                {"platform": "twitter", "accountId": "acc_1"},
                {"platform": "linkedin", "accountId": "acc_2"},
            ],
            "scheduledFor": "2026-03-14T12:00:00.000Z",
        }
    ]

    normalized = _normalize_posts(raw_items)

    assert len(normalized) == 2
    assert normalized[0]["post_type_name"] == "twitter"
    assert normalized[0]["external_id"] == "post_social_2::twitter"
    assert normalized[1]["post_type_name"] == "linkedin"
    assert normalized[1]["external_id"] == "post_social_2::linkedin"


def test_fetch_getlate_posts_uses_offset_pagination(monkeypatch):
    requested_offsets = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, headers, params, timeout):
        requested_offsets.append(params.get("offset"))
        if params.get("offset") == 0:
            return FakeResponse(
                {
                    "posts": [
                        {
                            "id": f"post_{index}",
                            "content": f"Post {index}",
                            "status": "scheduled",
                        }
                        for index in range(1, 101)
                    ]
                }
            )
        return FakeResponse({"posts": []})

    monkeypatch.setattr("app.post_ingestion.requests.get", fake_get)

    app = create_app("testing")
    app.config["LATE_API_BASE_URL"] = "https://getlate.dev/api/v1"

    class FakeCalendar:
        id = 1
        source_profile_id = "prof_123"

        @staticmethod
        def get_api_key():
            return "secret"

    with app.app_context():
        posts = _fetch_getlate_posts(FakeCalendar())

    assert len(posts) == 100
    assert requested_offsets[:2] == [0, 100]


def test_fetch_ghost_posts_with_admin_key_uses_admin_endpoint(monkeypatch):
    app = create_app("testing")

    captured = {"url": None, "auth": None, "params": None}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "posts": [
                    {
                        "id": "ghost_admin_1",
                        "title": "Scheduled Email",
                        "status": "scheduled",
                        "published_at": "2026-03-15T09:00:00.000Z",
                        "email_only": True,
                    }
                ]
            }

    def fake_get(url, headers=None, params=None, timeout=20):
        captured["url"] = url
        captured["auth"] = headers.get("Authorization") if headers else None
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setattr("app.post_ingestion.requests.get", fake_get)

    class FakeCalendar:
        id = 1
        source_profile_id = "https://example.com"

        @staticmethod
        def get_api_key():
            return "id:0123456789abcdef0123456789abcdef"

    with app.app_context():
        posts = _fetch_ghost_posts(FakeCalendar())

    assert len(posts) == 1
    assert captured["url"].endswith("/ghost/api/admin/posts/")
    assert captured["auth"].startswith("Ghost ")
    assert captured["params"]["filter"] == "status:[scheduled,published,sent]"
    assert posts[0]["post_type_name"] == "Email Only"


def test_fetch_ghost_posts_maps_401_to_helpful_error(monkeypatch):
    app = create_app("testing")

    class FakeResponse:
        status_code = 401

        def raise_for_status(self):
            raise requests.HTTPError(response=self)

        def json(self):
            return {"errors": [{"message": "Unauthorized"}]}

    def fake_get(url, params, timeout):
        return FakeResponse()

    monkeypatch.setattr("app.post_ingestion.requests.get", fake_get)

    class FakeCalendar:
        id = 2
        source_profile_id = "https://example.com"

        @staticmethod
        def get_api_key():
            return "validcontentkey"

    with app.app_context():
        try:
            _fetch_ghost_posts(FakeCalendar())
            assert False, "Expected RuntimeError"
        except RuntimeError as exc:
            assert str(exc) == (
                "Ghost fetch failed: unauthorized (401). Check blog URL and use a valid "
                "Ghost Content API key."
            )
