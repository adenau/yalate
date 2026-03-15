from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
import re
import time
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


def _normalize_title(item: dict[str, Any], prefer_title_first: bool = False) -> str:
    if prefer_title_first:
        title = item.get("title") or item.get("name")
        if isinstance(title, str) and title.strip():
            return title.strip()[:100]

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


def _extract_getlate_platform_targets(item: dict[str, Any]) -> list[tuple[str, str | None]]:
    platforms = item.get("platforms")
    if isinstance(platforms, list):
        extracted: list[tuple[str, str | None]] = []
        for entry in platforms:
            if isinstance(entry, dict):
                platform_value = entry.get("platform")
                if isinstance(platform_value, str) and platform_value.strip():
                    platform_slug = platform_value.strip().lower()
                    platform_status = entry.get("status")
                    if isinstance(platform_status, str) and platform_status.strip():
                        extracted.append((platform_slug, platform_status.strip().lower()))
                    else:
                        extracted.append((platform_slug, None))
            elif isinstance(entry, str) and entry.strip():
                extracted.append((entry.strip().lower(), None))

        unique_platforms = list(dict.fromkeys(extracted))
        if unique_platforms:
            return unique_platforms

    direct_platform = item.get("platform")
    if isinstance(direct_platform, str) and direct_platform.strip():
        return [(direct_platform.strip().lower(), None)]

    return []


def _normalize_posts(
    raw_items: list[dict[str, Any]],
    prefer_title_first: bool = False,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for item in raw_items:
        external_id = item.get("_id") or item.get("id") or item.get("postId")
        if not external_id:
            continue

        status_raw = item.get("status")
        if not isinstance(status_raw, str) or not status_raw.strip():
            status_raw = "scheduled"

        normalized_status = status_raw.strip().lower()

        platform_targets = _extract_getlate_platform_targets(item)

        scheduled_for = (
            _parse_datetime(item.get("scheduledFor"))
            or _parse_datetime(item.get("scheduledAt"))
            or _parse_datetime(item.get("scheduled_for"))
            or _parse_datetime(item.get("scheduled_at"))
            or _parse_datetime(item.get("publishAt"))
            or _parse_datetime(item.get("published_at"))
        )

        published_at = (
            _parse_datetime(item.get("publishedAt"))
            or _parse_datetime(item.get("published_at"))
        )

        if item.get("email_only") is True:
            normalized.append(
                {
                    "external_id": str(external_id),
                    "title": _normalize_title(item, prefer_title_first=prefer_title_first),
                    "status": normalized_status,
                    "post_type_name": "Email Only",
                    "scheduled_for": scheduled_for,
                    "published_at": published_at,
                }
            )
            continue

        if item.get("email_only") is False and not platform_targets:
            normalized.append(
                {
                    "external_id": str(external_id),
                    "title": _normalize_title(item, prefer_title_first=prefer_title_first),
                    "status": normalized_status,
                    "post_type_name": "Post",
                    "scheduled_for": scheduled_for,
                    "published_at": published_at,
                }
            )
            continue

        if platform_targets:
            for platform_slug, platform_status in platform_targets:
                platform_name = platform_slug.strip().lower()
                if not platform_name:
                    continue

                normalized.append(
                    {
                        "external_id": f"{external_id}::{platform_name}",
                        "title": _normalize_title(item, prefer_title_first=prefer_title_first),
                        "status": platform_status or normalized_status,
                        "post_type_name": platform_name,
                        "scheduled_for": scheduled_for,
                        "published_at": published_at,
                    }
                )
            continue

        raw_type_name = item.get("type")
        if isinstance(raw_type_name, str) and raw_type_name.strip():
            post_type_name = raw_type_name.strip()
        else:
            post_type_name = "Post"

        normalized.append(
            {
                "external_id": str(external_id),
                "title": _normalize_title(item, prefer_title_first=prefer_title_first),
                "status": normalized_status,
                "post_type_name": post_type_name,
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

    base_url = current_app.config["LATE_API_BASE_URL"].rstrip("/")
    current_app.logger.info(
        "Syncing Late posts for calendar_id=%s profile_id=%s",
        calendar.id,
        calendar.source_profile_id,
    )

    seen_external_ids: set[str] = set()
    collected_items: list[dict[str, Any]] = []
    limit = 100
    max_pages = 50

    pagination_modes = ["offset", "page"]

    for pagination_mode in pagination_modes:
        consecutive_no_new_pages = 0

        for page_index in range(max_pages):
            if pagination_mode == "offset":
                pagination_params = {"offset": page_index * limit}
            else:
                pagination_params = {"page": page_index + 1}

            params = {
                "profileId": calendar.source_profile_id,
                "limit": limit,
                **pagination_params,
            }

            current_app.logger.info(
                "Late posts request calendar_id=%s mode=%s page_index=%s params=%s",
                calendar.id,
                pagination_mode,
                page_index,
                pagination_params,
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
                raise RuntimeError(f"Late fetch failed: {exc}") from exc

            payload = response.json()
            if not isinstance(payload, dict):
                break

            page_items = _extract_items(payload)
            if not page_items:
                break

            current_app.logger.info(
                "Late posts response calendar_id=%s mode=%s page_index=%s count=%s",
                calendar.id,
                pagination_mode,
                page_index,
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
                consecutive_no_new_pages += 1
            else:
                consecutive_no_new_pages = 0

            if len(page_items) < limit:
                break

            if consecutive_no_new_pages >= 2:
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

    is_admin_key = ":" in api_key
    try:
        if is_admin_key:
            admin_jwt = _build_ghost_admin_jwt(api_key)
            response = requests.get(
                f"{base_url}/ghost/api/admin/posts/",
                headers={"Authorization": f"Ghost {admin_jwt}"},
                params={
                    "limit": "all",
                    "formats": "plaintext",
                    "include": "newsletter,email",
                    "filter": "status:[scheduled,published,sent]",
                },
                timeout=20,
            )
        else:
            response = requests.get(
                f"{base_url}/ghost/api/content/posts/",
                params={"key": api_key, "limit": "all", "formats": "plaintext"},
                timeout=20,
            )

        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code == 401:
            if is_admin_key:
                raise RuntimeError(
                    "Ghost fetch failed: unauthorized (401). Check Ghost Admin API key and blog URL."
                ) from exc
            raise RuntimeError(
                "Ghost fetch failed: unauthorized (401). Check blog URL and use a valid "
                "Ghost Content API key."
            ) from exc
        if status_code is not None:
            raise RuntimeError(f"Ghost fetch failed with status {status_code}") from exc
        raise RuntimeError("Ghost fetch failed with HTTP error") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Ghost fetch failed: {exc.__class__.__name__}") from exc

    payload = response.json()
    if not isinstance(payload, dict):
        return []

    return _normalize_posts(_extract_items(payload), prefer_title_first=True)


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _build_ghost_admin_jwt(admin_api_key: str) -> str:
    try:
        key_id, secret_hex = admin_api_key.split(":", 1)
        secret_bytes = bytes.fromhex(secret_hex)
    except ValueError as exc:
        raise RuntimeError("Ghost fetch failed: invalid admin API key format") from exc

    if not key_id or not secret_bytes:
        raise RuntimeError("Ghost fetch failed: invalid admin API key format")

    issued_at = int(time.time())
    expires_at = issued_at + 300

    header_segment = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT", "kid": key_id}, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    payload_segment = _base64url_encode(
        json.dumps({"iat": issued_at, "exp": expires_at, "aud": "/admin/"}, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(secret_bytes, signing_input, hashlib.sha256).digest()
    signature_segment = _base64url_encode(signature)

    return f"{header_segment}.{payload_segment}.{signature_segment}"


def _validate_getlate_credentials(api_key: str, profile_id: str) -> None:
    base_url = current_app.config["LATE_API_BASE_URL"].rstrip("/")

    try:
        response = requests.get(
            f"{base_url}/posts",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"profileId": profile_id, "limit": 1, "offset": 0},
            timeout=20,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code == 401:
            raise RuntimeError("Late credentials are unauthorized (401)") from exc
        if status_code == 403:
            raise RuntimeError("Late credentials are forbidden (403)") from exc
        if status_code is not None:
            raise RuntimeError(f"Late credential check failed with status {status_code}") from exc
        raise RuntimeError("Late credential check failed with HTTP error") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Late credential check failed: {exc.__class__.__name__}") from exc


def _validate_ghost_credentials(api_key: str, blog_url: str) -> None:
    base_url = blog_url.rstrip("/")
    if not base_url:
        raise RuntimeError("Ghost credential check failed: missing blog URL")

    is_admin_key = ":" in api_key

    try:
        if is_admin_key:
            admin_jwt = _build_ghost_admin_jwt(api_key)
            response = requests.get(
                f"{base_url}/ghost/api/admin/posts/",
                headers={"Authorization": f"Ghost {admin_jwt}"},
                params={"limit": 1},
                timeout=20,
            )
        else:
            response = requests.get(
                f"{base_url}/ghost/api/content/posts/",
                params={"key": api_key, "limit": 1, "formats": "plaintext"},
                timeout=20,
            )

        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code == 401:
            if is_admin_key:
                raise RuntimeError(
                    "Ghost credential check failed: unauthorized (401). "
                    "Check blog URL and Admin API key."
                ) from exc
            raise RuntimeError(
                "Ghost credential check failed: unauthorized (401). "
                "Check blog URL and Content API key."
            ) from exc
        if status_code == 404:
            raise RuntimeError(
                "Ghost credential check failed: endpoint not found (404). "
                "Check blog URL."
            ) from exc
        if status_code is not None:
            raise RuntimeError(f"Ghost credential check failed with status {status_code}") from exc
        raise RuntimeError("Ghost credential check failed with HTTP error") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Ghost credential check failed: {exc.__class__.__name__}") from exc


def validate_calendar_credentials(
    source: CalendarSource,
    api_key: str,
    source_profile_id: str | None = None,
) -> None:
    if not api_key:
        raise RuntimeError("Credential check failed: missing api_key")

    if source == CalendarSource.GETLATE:
        if not source_profile_id:
            raise RuntimeError("Credential check failed: missing Late profile_id")
        _validate_getlate_credentials(api_key, source_profile_id)
        return

    if source == CalendarSource.GHOST_BLOG:
        if not source_profile_id:
            raise RuntimeError("Credential check failed: missing Ghost blog URL")
        _validate_ghost_credentials(api_key, source_profile_id)
        return

    raise RuntimeError("Credential check failed: source not supported")


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
