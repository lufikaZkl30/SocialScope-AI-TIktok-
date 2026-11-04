"""Tests use small synthetic strings written for testing only; they are not analysis results."""
import io
import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as app_module  # noqa: E402
from app import create_app  # noqa: E402
from analysis.preprocessing import normalize_text  # noqa: E402
from analysis.sentiment import evaluate, score_text  # noqa: E402
from integrations.tiktok import (  # noqa: E402
    clear_account_tokens,
    exchange_authorization_code,
    get_account_videos,
    store_account_tokens,
    validate_tiktok_url,
)


class TikTokConfig(__import__("config").Config):
    TIKTOK_CLIENT_KEY = "test-client-key"
    TIKTOK_CLIENT_SECRET = "test-client-secret"
    TIKTOK_REDIRECT_URI = "http://localhost:5173/api/tiktok/callback"
    TIKTOK_FRONTEND_URL = "http://localhost:5173/"


@pytest.fixture()
def client():
    return create_app().test_client()


def upload(client, text, name="c.csv", **form):
    data = {"file": (io.BytesIO(text.encode("utf-8")), name), **form}
    return client.post("/api/analyze-csv", data=data, content_type="multipart/form-data")


def test_health(client):
    result = client.get("/api/health").get_json()
    assert result["ok"]
    assert result["data"]["integrations"]["tiktok_api"]["configured"] is False
    assert result["data"]["integrations"]["tiktok_account"]["configured"] is False


def test_sentiment_baseline():
    normalize = normalize_text
    assert score_text(normalize("Videonya bagus bangettt 😍"))[0] == "positive"
    assert score_text(normalize("gak bagus, jelek"))[0] == "negative"
    assert score_text(normalize("tidak jelek"))[0] == "positive"
    assert score_text(normalize("lagi makan siang"))[0] == "neutral"


def test_evaluate_requires_labels():
    assert evaluate(["", "x"], ["positive", "neutral"]) is None
    result = evaluate(["positive", "negative"], ["positive", "positive"])
    assert result["n_labeled"] == 2 and result["accuracy"] == 0.5


def test_csv_full_flow(client):
    rows = ["comment,timestamp,video_id,username,label"]
    for i in range(30):
        rows.append(f"Cek link di bio ya diskon gede!! wa 0812345678{i % 10},2025-01-01 10:0{i % 3}:00,v1,user{i},neutral")
    rows += ["Videonya bagus banget,2025-01-01 12:00:00,v2,a,positive",
             "Jelek banget sampah,2025-01-02 12:00:00,v2,b,negative",
             "Aku suka konten ini sangat menghibur,2025-01-03 12:00:00,v1,c,positive",
             "Aku suka konten ini sangat menghibur!!!,2025-01-03 12:01:00,v2,d,positive",
             ",2025-01-03,v1,e,neutral"]
    response = upload(client, "\n".join(rows))
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["data"]
    assert result["summary"]["total_comments"] == 34
    assert result["quality"]["empty_comments_removed"] == 1
    assert result["quality"]["username_column_ignored"]
    assert result["summary"]["promotional_signals"] >= 30
    assert result["promotional"]["disclaimer"]
    assert result["similarity"]["counts"]["comments_in_any_repeat"] >= 30
    assert result["sentiment"]["evaluation"]["n_labeled"] == 34
    assert result["coordination"]["time"] is not None
    assert "user0" not in str(result) and "08123456780" not in str(result)
    assert any("[phone]" in comment["text"] for comment in result["comments"])
    indicators = {item["id"]: item for item in result["coordination"]["indicators"]}
    assert indicators["cross_video"]["available"]
    assert indicators["repeated_text"]["strength"] in ("moderate", "strong")


def test_csv_errors(client):
    assert upload(client, "").status_code == 422
    assert upload(client, "foo,bar\n1,2").get_json()["error"]["code"] == "missing_column"
    assert upload(client, "comment\n").get_json()["error"]["code"] == "no_rows"
    assert upload(client, "comment\n,\n  \n").status_code == 422
    assert upload(client, "comment\nhi", name="x.xlsx").status_code == 415
    assert client.post("/api/analyze-csv").status_code == 400
    assert upload(client, "comment\nhi", similarity_threshold="5").status_code == 400
    assert client.get("/api/nope").status_code == 404


def test_csv_malformed_rows_and_semicolons(client):
    response = upload(client, "comment;timestamp\nhalo semua;2025-01-01\nbagus;2025-01-01;extra;cols\nmantap;x")
    result = response.get_json()["data"]
    assert response.status_code == 200 and result["quality"]["malformed_rows_skipped"] == 1
    assert result["quality"]["timestamps_unparseable"] >= 1
    assert result["coordination"]["time"] is None


def test_row_limit():
    class Small(__import__("config").Config):
        MAX_ROWS = 3

    client = create_app(Small).test_client()
    response = upload(client, "comment\na\nb\nc\nd")
    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "too_many_rows"


@pytest.mark.parametrize("url,valid,kind", [
    ("https://www.tiktok.com/@some.user/video/7234567890123456789?is_from_webapp=1", True, "video"),
    ("tiktok.com/@u/video/7234567890123456789", True, "video"),
    ("https://vm.tiktok.com/ZSabc12345/", True, "short_link"),
    ("https://www.tiktok.com/@user", False, None),
    ("https://evil-tiktok.com/@u/video/7234567890123456789", False, None),
    ("https://tiktok.com.evil.com/@u/video/7234567890123456789", False, None),
    ("javascript:alert(1)", False, None),
    ("******www.tiktok.com/@u/video/7234567890123456789", False, None),
    ("", False, None),
])
def test_url_validation(url, valid, kind):
    valid_url, info = validate_tiktok_url(url)
    assert valid_url is valid
    if valid:
        assert info["url_type"] == kind and "?" not in info["normalized_url"]


def test_url_endpoint_is_honest(client):
    response = client.post("/api/analyze-url", json={
        "url": "https://www.tiktok.com/@u/video/7234567890123456789"
    })
    result = response.get_json()["data"]
    assert response.status_code == 200
    assert result["content_analyzed"] is False and result["comments_retrieved"] == 0
    assert result["integration"]["configured"] is False
    assert result["analysis_status"] == "validated_only"
    assert client.post("/api/analyze-url", json={"url": "https://example.com"}).status_code == 422
    assert client.post("/api/analyze-url", data="nope").status_code == 400


def test_tiktok_login_requires_developer_app_config():
    client = create_app().test_client()
    assert client.get("/api/tiktok/status").get_json()["data"]["configured"] is False
    response = client.get("/api/tiktok/login")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "tiktok_login_not_configured"


def test_tiktok_login_redirects_with_video_list_scope():
    client = create_app(TikTokConfig).test_client()
    response = client.get("/api/tiktok/login")
    assert response.status_code == 302
    query = parse_qs(urlparse(response.location).query)
    assert urlparse(response.location).path == "/v2/auth/authorize/"
    assert query["client_key"] == ["test-client-key"]
    assert query["scope"] == ["video.list"]
    assert query["redirect_uri"] == [TikTokConfig.TIKTOK_REDIRECT_URI]
    with client.session_transaction() as browser_session:
        assert query["state"] == [browser_session["tiktok_oauth_state"]]


def test_tiktok_callback_checks_state_and_never_returns_tokens(monkeypatch):
    client = create_app(TikTokConfig).test_client()
    with client.session_transaction() as browser_session:
        browser_session["tiktok_oauth_state"] = "expected-state"

    def fake_exchange(config, code):
        assert config is TikTokConfig
        assert code == "authorization-code"
        return {
            "access_token": "private-access-token",
            "refresh_token": "private-refresh-token",
            "open_id": "test-open-id",
            "scope": "video.list",
            "expires_at": time.time() + 3600,
            "refresh_expires_at": time.time() + 7200,
        }

    monkeypatch.setattr(app_module, "exchange_authorization_code", fake_exchange)
    rejected = client.get("/api/tiktok/callback?state=wrong&code=authorization-code")
    assert "reason=invalid_state" in rejected.location

    with client.session_transaction() as browser_session:
        browser_session["tiktok_oauth_state"] = "expected-state"
    connected = client.get("/api/tiktok/callback?state=expected-state&code=authorization-code")
    assert connected.status_code == 302 and "tiktok=connected" in connected.location
    status = client.get("/api/tiktok/status").get_json()["data"]
    assert status["connected"] and status["scopes"] == ["video.list"]
    assert "private-access-token" not in str(status)
    assert "private-refresh-token" not in str(status)

    disconnected = client.post("/api/tiktok/disconnect").get_json()["data"]
    assert disconnected["connected"] is False
    assert client.get("/api/tiktok/status").get_json()["data"]["connected"] is False


@pytest.mark.parametrize("payload", [
    {"cursor": -1},
    {"cursor": True},
    {"max_count": 0},
    {"max_count": 21},
    {"max_count": True},
    [],
])
def test_tiktok_video_list_rejects_invalid_input(payload):
    response = create_app(TikTokConfig).test_client().post("/api/tiktok/videos", json=payload)
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_tiktok_video_list_requires_connected_account():
    response = create_app(TikTokConfig).test_client().post("/api/tiktok/videos", json={})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "tiktok_not_connected"


def test_tiktok_video_list_route_returns_account_videos(monkeypatch):
    client = create_app(TikTokConfig).test_client()
    with client.session_transaction() as browser_session:
        browser_session["tiktok_session_id"] = "test-session"
    calls = []

    def fake_get_videos(config, session_id, cursor, max_count):
        calls.append((config, session_id, cursor, max_count))
        return {"videos": [{"id": "123", "create_time": 1700000000}], "cursor": 20, "has_more": True}

    monkeypatch.setattr(app_module, "get_account_videos", fake_get_videos)
    response = client.post("/api/tiktok/videos", json={"cursor": 10, "max_count": 15})
    assert response.status_code == 200
    assert response.get_json()["data"]["videos"][0]["id"] == "123"
    assert calls == [(TikTokConfig, "test-session", 10, 15)]


def test_exchange_authorization_code_uses_server_credentials(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"data": {
                "access_token": "private-access-token",
                "refresh_token": "private-refresh-token",
                "open_id": "test-open-id",
                "scope": "user.info.basic,video.list",
                "expires_in": 3600,
                "refresh_expires_in": 7200,
                "error_code": 0,
            }}).encode()

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://open.tiktokapis.com/v2/oauth/token/"
        assert request.get_header("Content-type") == "application/x-www-form-urlencoded"
        assert timeout == 20
        body = parse_qs(request.data.decode())
        assert body["client_key"] == ["test-client-key"]
        assert body["client_secret"] == ["test-client-secret"]
        assert body["code"] == ["one-time-code"]
        assert body["grant_type"] == ["authorization_code"]
        assert body["redirect_uri"] == [TikTokConfig.TIKTOK_REDIRECT_URI]
        return Response()

    monkeypatch.setattr("integrations.tiktok.urlopen", fake_urlopen)
    result = exchange_authorization_code(TikTokConfig, "one-time-code")
    assert result["access_token"] == "private-access-token"
    assert result["refresh_token"] == "private-refresh-token"
    assert result["open_id"] == "test-open-id"
    assert set(result["scope"].split(",")) == {"user.info.basic", "video.list"}


def test_account_video_request_uses_authorized_access_token(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"data": {
                "videos": [{"id": "123", "create_time": 1700000000}],
                "cursor": 20,
                "has_more": True,
            }}).encode()

    def fake_urlopen(request, timeout):
        assert request.full_url.startswith("https://open.tiktokapis.com/v2/video/list/?fields=")
        assert request.get_header("Authorization") == "Bearer private-access-token"
        assert json.loads(request.data) == {"cursor": 15, "max_count": 20}
        assert timeout == 20
        return Response()

    monkeypatch.setattr("integrations.tiktok.urlopen", fake_urlopen)
    store_account_tokens("video-test-session", {
        "access_token": "private-access-token",
        "refresh_token": "private-refresh-token",
        "open_id": "test-open-id",
        "scope": "video.list",
        "expires_at": time.time() + 3600,
        "refresh_expires_at": time.time() + 7200,
    })
    try:
        result = get_account_videos(TikTokConfig, "video-test-session", cursor=15, max_count=20)
    finally:
        clear_account_tokens("video-test-session")
    assert result["videos"][0]["id"] == "123"
    assert result["has_more"] is True


def test_time_burst_is_detected_and_reported_in_utc(client):
    rows = ["comment,timestamp"]
    for i in range(30):
        rows.append(f"komentar biasa nomor {i} tentang video,2025-05-01 {8 + (i * 20) // 60:02d}:{(i * 20) % 60:02d}:00")
    for i in range(25):
        rows.append(f"wajib nonton sampai habis luar biasa,2025-05-01 12:0{i % 5}:{i:02d}")
    result = upload(client, "\n".join(rows)).get_json()["data"]
    time_analysis = result["coordination"]["time"]
    assert max(point["count"] for point in time_analysis["series"]) >= 25
    assert time_analysis["bursts"] and time_analysis["bursts"][0]["comments"] >= 25
    assert time_analysis["bursts"][0]["share_also_repeated_text"] > 0.9
    assert time_analysis["first"].endswith("Z")
    assert time_analysis["bursts"][0]["bucket_start"].endswith("Z")
    indicators = {item["id"]: item for item in result["coordination"]["indicators"]}
    assert indicators["time_concentration"]["strength"] in ("moderate", "strong")
