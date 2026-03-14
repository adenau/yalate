from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any

import requests
from flask import current_app

from .extensions import db
from .models import Calendar, CalendarSource, Post, PostType


@dataclass
class SyncResult:
    fetched: int = 0
    created: int = 0
    updated: int = 0


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed


def _slugify(value: str) -> str:
    return "-".join(value.strip().lower().replace("_", " ").split())


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("posts", "data", "results", "items"):
        maybe_list = payload.get(key)
        if isinstance(maybe_list, list):
            return [item for item in maybe_list if isinstance(item, dict)]
    return []


def _normalize_title(item: dict[str, Any]) -> str:
    content = item.get("plaintext") or item.get("content") or item.get("html")
    content_text = _to_text_with_line_breaks(content)
    if content_text:
        return content_text[:100]

    title = item.get("title") or item.get("name")
    if isinstance(title, str) and title.strip():
        return title.strip()[:100]

    return "Untitled post"


def _to_text_with_line_breaks(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    text = value.strip()
    if not text:
        return ""

    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _normalize_posts(raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for item in raw_items:
        external_id = item.get("_id") or item.get("id") or item.get("postId")
        if not external_id:
            continue

        status = item.get("status")
        if not isinstance(status, str) or not status.strip():
            status = "scheduled"

        post_type_name = item.get("type")
        if not isinstance(post_type_name, str) or not post_type_name.strip():
            post_type_name = "General"

        scheduled_for = (
            _parse_datetime(item.get("scheduledFor"))
            or _parse_datetime(item.get("scheduled_for"))
            or _parse_datetime(item.get("scheduled_at"))
            or _parse_datetime(item.get("published_at"))
        )

        published_at = (
            _parse_datetime(item.get("publishedAt"))
            or _parse_datetime(item.get("published_at"))
        )

        normalized.append(
            {
                "external_id": str(external_id),
                "title": _normalize_title(item),
                "status": status.strip().lower(),
                "post_type_name": post_type_name.strip(),
                "scheduled_for": scheduled_for,
                "published_at": published_at,
            }
        )

    return normalized


def _get_or_create_post_type(name: str) -> PostType:
    slug = _slugify(name)
    existing = db.session.execute(db.select(PostType).filter_by(slug=slug)).scalar_one_or_none()
    if existing is not None:
        return existing

    post_type = PostType(name=name, slug=slug)
    db.session.add(post_type)
    db.session.flush()
    return post_type


def _fetch_getlate_posts(calendar: Calendar) -> list[dict[str, Any]]:
    api_key = calendar.get_api_key()
    if not api_key:
        return []

    base_url = current_app.config["GETLATE_API_BASE_URL"].rstrip("/")
    current_app.logger.info(
        "Syncing GetLate posts for calendar_id=%s profile_id=%s",
        calendar.id,
        calendar.source_profile_id,
    )

    seen_external_ids: set[str] = set()
    collected_items: list[dict[str, Any]] = []
    limit = 100
    max_pages = 50

    for page_index in range(max_pages):
        offset = page_index * limit
        params = {
            "profileId": calendar.source_profile_id,
            "limit": limit,
            "offset": offset,
        }

        current_app.logger.info(
            "GetLate posts request calendar_id=%s offset=%s limit=%s",
            calendar.id,
            offset,
            limit,
        )

        try:
            response = requests.get(
                f"{base_url}/posts",
                headers={"Authorization": f"Bearer {api_key}"},
                params=params,
                timeout=20,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"GetLate fetch failed: {exc}") from exc

        payload = response.json()
        if not isinstance(payload, dict):
            break

        page_items = _extract_items(payload)
        if not page_items:
            break

        current_app.logger.info(
            "GetLate posts response calendar_id=%s offset=%s count=%s",
            calendar.id,
            offset,
            len(page_items),
        )

        new_count = 0
        for item in page_items:
            external_id = item.get("_id") or item.get("id") or item.get("postId")
            if external_id is None:
                continue

            external_id_str = str(external_id)
            if external_id_str in seen_external_ids:
                continue

            seen_external_ids.add(external_id_str)
            collected_items.append(item)
            new_count += 1

        if new_count == 0:
            break

        if len(page_items) < limit:
            break

    return _normalize_posts(collected_items)


def _fetch_ghost_posts(calendar: Calendar) -> list[dict[str, Any]]:
    api_key = calendar.get_api_key()
    if not api_key:
        return []

    base_url = (calendar.source_profile_id or current_app.config["GHOST_API_BASE_URL"] or "").rstrip("/")
    if not base_url:
        return []

    current_app.logger.info(
        "Syncing Ghost posts for calendar_id=%s base_url=%s",
        calendar.id,
        base_url,
    )

    try:
        response = requests.get(
            f"{base_url}/ghost/api/content/posts/",
            params={"key": api_key, "limit": "all", "formats": "plaintext"},
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Ghost fetch failed: {exc}") from exc

    payload = response.json()
    if not isinstance(payload, dict):
        return []

    return _normalize_posts(_extract_items(payload))


def fetch_posts_for_calendar(calendar: Calendar) -> list[dict[str, Any]]:
    if calendar.source == CalendarSource.GETLATE:
        return _fetch_getlate_posts(calendar)
    if calendar.source == CalendarSource.GHOST_BLOG:
        return _fetch_ghost_posts(calendar)

    return []


def sync_calendar_posts(calendar: Calendar) -> SyncResult:
    now = datetime.now(UTC)
    normalized_posts = fetch_posts_for_calendar(calendar)
    result = SyncResult(fetched=len(normalized_posts))
    current_app.logger.info(
        "Fetched %s posts for calendar_id=%s source=%s",
        result.fetched,
        calendar.id,
        calendar.source.value,
    )

    for item in normalized_posts:
        post_type = _get_or_create_post_type(item["post_type_name"])

        existing_post = db.session.execute(
            db.select(Post).filter_by(
                calendar_id=calendar.id,
                external_id=item["external_id"],
            )
        ).scalar_one_or_none()

        if existing_post is None:
            new_post = Post(
                calendar_id=calendar.id,
                post_type_id=post_type.id,
                external_id=item["external_id"],
                title=item["title"],
                status=item["status"],
                scheduled_for=item["scheduled_for"],
                published_at=item["published_at"],
            )
            db.session.add(new_post)
            result.created += 1
            continue

        existing_post.post_type_id = post_type.id
        existing_post.title = item["title"]
        existing_post.status = item["status"]
        existing_post.scheduled_for = item["scheduled_for"]
        existing_post.published_at = item["published_at"]
        existing_post.updated_at = now
        result.updated += 1

    db.session.commit()
    current_app.logger.info(
        "Sync complete for calendar_id=%s created=%s updated=%s",
        calendar.id,
        result.created,
        result.updated,
    )
    return result
