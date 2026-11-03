"""TikTok URL validation, Research API video queries, and the comment-source placeholder.

* `validate_tiktok_url` only checks the FORMAT of a URL. It makes no network request.
* Research API queries return public video metadata and require approved API access.
* No scraping and no access-restriction bypass exists in this project, by design.
* The Research API integration does not retrieve comments. Use authorized credentials only.
"""
import json
import re
from abc import ABC, abstractmethod
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ALLOWED_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}
VIDEO_PATH = re.compile(r"^/@[\w.\-]{1,64}/video/(\d{8,25})/?$")
LEGACY_PATH = re.compile(r"^/v/(\d{8,25})(?:\.html)?/?$")
SHORT_PATH = re.compile(r"^/(?:t/)?[A-Za-z0-9]{6,20}/?$")
RESEARCH_VIDEO_FIELDS = ("id", "like_count", "view_count", "comment_count", "share_count")
RESEARCH_VIDEO_QUERY_URL = "https://open.tiktokapis.com/v2/research/video/query/"


def validate_tiktok_url(raw: str):
    """Return (ok, details). Never raises; `details['reason']` explains a failure."""
    raw = (raw or "").strip()
    if not raw:
        return False, {"reason": "Enter a TikTok video URL."}
    if len(raw) > 500:
        return False, {"reason": "The URL is too long."}
    if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
        raw = "https://" + raw
    try:
        u = urlparse(raw)
        host, port = (u.hostname or "").lower(), u.port
    except ValueError:
        return False, {"reason": "This is not a valid URL."}
    if u.scheme not in ("http", "https"):
        return False, {"reason": "Only http and https links are supported."}
    if u.username or u.password or port not in (None, 80, 443):
        return False, {"reason": "URLs with credentials or custom ports are not accepted."}
    if host not in ALLOWED_HOSTS:
        return False, {"reason": f"'{host or raw}' is not a supported TikTok domain. "
                                 "Supported: tiktok.com, www.tiktok.com, m.tiktok.com, vm.tiktok.com, vt.tiktok.com."}
    path = u.path or "/"
    if host in ("vm.tiktok.com", "vt.tiktok.com") or path.startswith("/t/"):
        if not SHORT_PATH.match(path):
            return False, {"reason": "This looks like a TikTok short link, but the path format is not recognised."}
        return True, {"url_type": "short_link", "video_id": None, "normalized_url": f"https://{host}{path}",
                      "note": "Short links must be resolved by TikTok to reveal the video ID. "
                              "This app does not follow redirects, so the video ID is unknown."}
    m = VIDEO_PATH.match(path) or LEGACY_PATH.match(path)
    if not m:
        return False, {"reason": "The link is on a TikTok domain but is not a video link. "
                                 "Expected a format like https://www.tiktok.com/@username/video/1234567890123456789."}
    return True, {"url_type": "video", "video_id": m.group(1), "normalized_url": f"https://{host}{path.rstrip('/')}"}


class CommentSource(ABC):
    """Interface for an authorized comment data source."""
    name = "unnamed"

    @abstractmethod
    def status(self) -> dict: ...

    @abstractmethod
    def fetch_comments(self, video_id: str) -> list: ...


class UnconfiguredSource(CommentSource):
    name = "none"

    def __init__(self, token_present=False):
        self.token_present = token_present

    def status(self):
        if self.token_present:
            return {"configured": False, "state": "comments_unavailable",
                    "message": "A TikTok API token is set for public video metadata queries. "
                               "This app does not retrieve comments."}
        return {"configured": False, "state": "not_configured",
                "message": "No TikTok comment connector is configured. Upload a CSV of comments you are "
                           "permitted to analyse."}

    def fetch_comments(self, video_id):
        raise NotImplementedError("No comment source is configured.")


def get_connector(config) -> CommentSource:
    return UnconfiguredSource(token_present=bool((config.TIKTOK_API_ACCESS_TOKEN or "").strip()))


class TikTokResearchApiError(Exception):
    def __init__(self, code, message, status, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


def research_api_status(config):
    configured = bool((config.TIKTOK_API_ACCESS_TOKEN or "").strip())
    return {
        "configured": configured,
        "videos_query_available": configured,
        "comments_available": False,
        "state": "configured" if configured else "not_configured",
        "message": (
            "TikTok Research API is configured for public video metadata queries. "
            "It does not retrieve comments."
            if configured else
            "Set TIKTOK_API_ACCESS_TOKEN in backend/.env to enable public video queries. "
            "TikTok Research API access must be approved; this API does not retrieve comments."
        ),
    }


def query_public_videos(config, query):
    token = (config.TIKTOK_API_ACCESS_TOKEN or "").strip()
    if not token:
        raise TikTokResearchApiError(
            "research_api_not_configured",
            "Configure an approved TikTok Research API access token in backend/.env.",
            503,
        )

    url = f"{RESEARCH_VIDEO_QUERY_URL}?{urlencode({'fields': ','.join(RESEARCH_VIDEO_FIELDS)})}"
    body = {
        "query": {
            "and": [
                {"operation": "IN", "field_name": "region_code", "field_values": query["region_codes"]},
                {"operation": "EQ", "field_name": "keyword", "field_values": [query["keyword"]]},
            ],
        },
        "max_count": query["max_count"],
        "cursor": query["cursor"],
        "start_date": query["start_date"],
        "end_date": query["end_date"],
        "is_random": False,
    }
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        messages = {
            401: "TikTok rejected the access token. Check that it is valid and not expired.",
            403: "TikTok denied access. Confirm that your app has Research API approval.",
            429: "TikTok rate limit reached. Wait before trying again.",
        }
        details = {"upstream_status": exc.code}
        try:
            upstream = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            upstream = {}
        upstream_error = upstream.get("error") if isinstance(upstream, dict) else None
        if isinstance(upstream_error, dict):
            upstream_code = upstream_error.get("code")
            upstream_message = upstream_error.get("message")
            if upstream_code:
                details["upstream_code"] = str(upstream_code)[:100]
            if exc.code not in messages and isinstance(upstream_message, str) and upstream_message:
                messages[exc.code] = upstream_message[:300]
        raise TikTokResearchApiError(
            "research_api_upstream_error",
            messages.get(exc.code, f"TikTok Research API returned HTTP {exc.code}."),
            502 if exc.code != 429 else 503,
            details,
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise TikTokResearchApiError(
            "research_api_unreachable",
            "Could not reach TikTok Research API. Try again later.",
            503,
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TikTokResearchApiError(
            "research_api_invalid_response",
            "TikTok Research API returned an unreadable response.",
            502,
        ) from exc

    if not isinstance(result, dict):
        raise TikTokResearchApiError(
            "research_api_invalid_response",
            "TikTok Research API returned an unexpected response.",
            502,
        )

    error = result.get("error")
    if isinstance(error, dict) and error.get("code") not in (None, "ok"):
        api_message = error.get("message")
        message = api_message[:300] if isinstance(api_message, str) and api_message else (
            "TikTok Research API rejected the query."
        )
        raise TikTokResearchApiError(
            "research_api_query_rejected",
            message,
            502,
            {"upstream_code": str(error["code"])[:100]},
        )

    data = result.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("videos"), list):
        raise TikTokResearchApiError(
            "research_api_invalid_response",
            "TikTok Research API returned an unexpected video result.",
            502,
        )
    return data
