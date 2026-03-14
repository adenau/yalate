from app import create_app
from app.post_ingestion import _fetch_getlate_posts, _normalize_posts


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
    app.config["GETLATE_API_BASE_URL"] = "https://getlate.dev/api/v1"

    class FakeCalendar:
        id = 1
        source_profile_id = "prof_123"

        @staticmethod
        def get_api_key():
            return "secret"

    with app.app_context():
        posts = _fetch_getlate_posts(FakeCalendar())

    assert len(posts) == 100
    assert requested_offsets == [0, 100]
