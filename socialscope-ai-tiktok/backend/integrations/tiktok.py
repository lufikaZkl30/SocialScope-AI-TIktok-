"""TikTok URL validation and the (currently unconfigured) comment-source connector.

* `validate_tiktok_url` only checks the FORMAT of a URL. It makes no network request.
* No scraping and no access-restriction bypass exists in this project, by design.
* To add a legitimate integration, subclass `CommentSource`, implement `fetch_comments`, and
  return it from `get_connector`. Use credentials/permissions you are actually authorized to use.
"""
import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse

ALLOWED_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}
VIDEO_PATH = re.compile(r"^/@[\w.\-]{1,64}/video/(\d{8,25})/?$")
LEGACY_PATH = re.compile(r"^/v/(\d{8,25})(?:\.html)?/?$")
SHORT_PATH = re.compile(r"^/(?:t/)?[A-Za-z0-9]{6,20}/?$")


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
            return {"configured": False, "state": "credentials_present_connector_missing",
                    "message": "An API token is set in the environment, but this project ships no connector that "
                               "uses it, so no comments can be retrieved. Implement a CommentSource for an API "
                               "you are authorized to use."}
        return {"configured": False, "state": "not_configured",
                "message": "No authorized TikTok API or data connector is configured, so automatic comment "
                           "retrieval is unavailable. Upload a CSV of comments you are permitted to analyse."}

    def fetch_comments(self, video_id):
        raise NotImplementedError("No comment source is configured.")


def get_connector(config) -> CommentSource:
    return UnconfiguredSource(token_present=bool(config.TIKTOK_API_ACCESS_TOKEN))
