"""TikTok URL validation, Login Kit, video-list access, and the comment-source placeholder.

* `validate_tiktok_url` only checks the FORMAT of a URL. It makes no network request.
* Video-list requests return metadata for the account that authorized the app.
* No scraping and no access-restriction bypass exists in this project, by design.
* The video-list API does not retrieve comments. Use authorized credentials only.
"""
import json
import re
import threading
import time
from abc import ABC, abstractmethod
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ALLOWED_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}
VIDEO_PATH = re.compile(r"^/@[\w.\-]{1,64}/video/(\d{8,25})/?$")
LEGACY_PATH = re.compile(r"^/v/(\d{8,25})(?:\.html)?/?$")
SHORT_PATH = re.compile(r"^/(?:t/)?[A-Za-z0-9]{6,20}/?$")
TIKTOK_AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"
TIKTOK_VIDEO_FIELDS = (
    "id",
    "create_time",
    "video_description",
    "share_url",
    "cover_image_url",
    "like_count",
    "view_count",
    "comment_count",
    "share_count",
)
_ACCOUNT_TOKENS = {}
_ACCOUNT_TOKENS_LOCK = threading.RLock()


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
    return UnconfiguredSource()


class TikTokApiError(Exception):
    def __init__(self, code, message, status, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details


def login_kit_status(config, session_id=None):
    configured = bool(config.TIKTOK_CLIENT_KEY and config.TIKTOK_CLIENT_SECRET
                      and config.TIKTOK_REDIRECT_URI)
    with _ACCOUNT_TOKENS_LOCK:
        tokens = _ACCOUNT_TOKENS.get(session_id) if session_id else None
    return {
        "configured": configured,
        "connected": bool(tokens),
        "required_scope": "video.list",
        "scopes": tokens["scope"].split(",") if tokens else [],
        "message": (
            "Connect TikTok to list videos from the authorized account."
            if configured else
            "Create a TikTok Developer app and set TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, "
            "and TIKTOK_REDIRECT_URI in backend/.env."
        ),
    }


def build_authorization_url(config, state):
    if not login_kit_status(config)["configured"]:
        raise TikTokApiError(
            "tiktok_login_not_configured",
            "Configure the TikTok Developer app credentials in backend/.env first.",
            503,
        )
    params = {
        "client_key": config.TIKTOK_CLIENT_KEY,
        "response_type": "code",
        "scope": "video.list",
        "redirect_uri": config.TIKTOK_REDIRECT_URI,
        "state": state,
    }
    return f"{TIKTOK_AUTHORIZE_URL}?{urlencode(params)}"


def _read_json_response(response):
    try:
        result = json.loads(response.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TikTokApiError(
            "tiktok_invalid_response",
            "TikTok returned an unreadable response.",
            502,
        ) from exc
    if not isinstance(result, dict):
        raise TikTokApiError(
            "tiktok_invalid_response",
            "TikTok returned an unexpected response.",
            502,
        )
    error = result.get("error")
    if isinstance(error, dict) and error.get("code") not in (None, "ok"):
        raise TikTokApiError(
            "tiktok_upstream_error",
            str(error.get("message") or "TikTok rejected the request.")[:300],
            502,
            {"upstream_code": str(error.get("code"))[:100]},
        )
    data = result.get("data")
    if isinstance(data, dict) and data.get("error_code") not in (None, 0, "0"):
        raise TikTokApiError(
            "tiktok_upstream_error",
            str(data.get("description") or data.get("message") or "TikTok rejected the request.")[:300],
            502,
            {"upstream_code": str(data["error_code"])[:100]},
        )
    return data if isinstance(data, dict) else result


def _send_request(request, error_code):
    try:
        with urlopen(request, timeout=20) as response:
            return _read_json_response(response)
    except HTTPError as exc:
        details = {"upstream_status": exc.code}
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        upstream_error = payload.get("error") if isinstance(payload, dict) else None
        message = {
            401: "TikTok rejected the authorization. Reconnect your account and try again.",
            403: "TikTok denied access. Confirm your app has the video.list scope approved.",
            429: "TikTok rate limit reached. Wait before trying again.",
        }.get(exc.code)
        if isinstance(upstream_error, dict):
            if upstream_error.get("code"):
                details["upstream_code"] = str(upstream_error["code"])[:100]
            upstream_message = upstream_error.get("message")
            if not message and isinstance(upstream_message, str) and upstream_message:
                message = upstream_message[:300]
        raise TikTokApiError(
            error_code,
            message or f"TikTok returned HTTP {exc.code}.",
            503 if exc.code == 429 else 502,
            details,
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise TikTokApiError(
            "tiktok_unreachable",
            "Could not reach TikTok. Check your connection and try again.",
            503,
        ) from exc


def _post_form(url, values, error_code):
    request = Request(
        url,
        data=urlencode(values).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    return _send_request(request, error_code)


def exchange_authorization_code(config, code):
    if not login_kit_status(config)["configured"]:
        raise TikTokApiError(
            "tiktok_login_not_configured",
            "Configure the TikTok Developer app credentials in backend/.env first.",
            503,
        )
    data = _post_form(TIKTOK_TOKEN_URL, {
        "client_key": config.TIKTOK_CLIENT_KEY,
        "client_secret": config.TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": config.TIKTOK_REDIRECT_URI,
    }, "tiktok_token_exchange_failed")
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    scopes = {scope.strip() for scope in str(data.get("scope", "")).split(",") if scope.strip()}
    if not isinstance(access_token, str) or not access_token or not isinstance(refresh_token, str) or not refresh_token:
        raise TikTokApiError(
            "tiktok_invalid_token_response",
            "TikTok did not return the access and refresh tokens required for this connection.",
            502,
        )
    if "video.list" not in scopes:
        raise TikTokApiError(
            "tiktok_scope_missing",
            "TikTok did not grant video.list. Enable that scope for your app and reconnect.",
            403,
        )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "open_id": data.get("open_id"),
        "scope": ",".join(sorted(scopes)),
        "expires_at": time.time() + int(data.get("expires_in", 86400)),
        "refresh_expires_at": time.time() + int(data.get("refresh_expires_in", 31536000)),
    }


def store_account_tokens(session_id, tokens):
    with _ACCOUNT_TOKENS_LOCK:
        _ACCOUNT_TOKENS[session_id] = tokens


def clear_account_tokens(session_id):
    with _ACCOUNT_TOKENS_LOCK:
        _ACCOUNT_TOKENS.pop(session_id, None)


def _refresh_account_token(config, tokens):
    if tokens["refresh_expires_at"] <= time.time():
        raise TikTokApiError(
            "tiktok_session_expired",
            "TikTok authorization expired. Reconnect your account.",
            401,
        )
    data = _post_form(TIKTOK_TOKEN_URL, {
        "client_key": config.TIKTOK_CLIENT_KEY,
        "client_secret": config.TIKTOK_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
    }, "tiktok_token_refresh_failed")
    access_token = data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise TikTokApiError(
            "tiktok_invalid_token_response",
            "TikTok did not return a refreshed access token. Reconnect your account.",
            502,
        )
    refreshed = {
        **tokens,
        "access_token": access_token,
        "refresh_token": data.get("refresh_token") or tokens["refresh_token"],
        "expires_at": time.time() + int(data.get("expires_in", 86400)),
        "refresh_expires_at": time.time() + int(data.get("refresh_expires_in", 31536000)),
    }
    return refreshed


def get_account_videos(config, session_id, cursor=0, max_count=20):
    with _ACCOUNT_TOKENS_LOCK:
        tokens = _ACCOUNT_TOKENS.get(session_id)
    if not tokens:
        raise TikTokApiError(
            "tiktok_not_connected",
            "Connect your TikTok account before loading its videos.",
            401,
        )

    if tokens["expires_at"] <= time.time() + 60:
        tokens = _refresh_account_token(config, tokens)
        store_account_tokens(session_id, tokens)

    url = f"{TIKTOK_VIDEO_LIST_URL}?{urlencode({'fields': ','.join(TIKTOK_VIDEO_FIELDS)})}"
    request = Request(
        url,
        data=json.dumps({"max_count": max_count, "cursor": cursor}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    data = _send_request(request, "tiktok_video_list_failed")
    if not isinstance(data.get("videos"), list):
        raise TikTokApiError(
            "tiktok_invalid_response",
            "TikTok returned an unexpected video list.",
            502,
        )
    return data
