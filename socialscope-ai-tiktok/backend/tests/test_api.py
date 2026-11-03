"""Tests use small synthetic strings written for testing only; they are not analysis results."""
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as app_module  # noqa: E402
from app import create_app  # noqa: E402
from analysis.preprocessing import normalize_text  # noqa: E402
from analysis.sentiment import evaluate, score_text  # noqa: E402
from integrations.tiktok import query_public_videos, validate_tiktok_url  # noqa: E402


@pytest.fixture()
def client():
    return create_app().test_client()


def upload(client, text, name="c.csv", **form):
    data = {"file": (io.BytesIO(text.encode("utf-8")), name), **form}
    return client.post("/api/analyze-csv", data=data, content_type="multipart/form-data")


def test_health(client):
    r = client.get("/api/health").get_json()
    assert r["ok"] and r["data"]["integrations"]["tiktok_api"]["configured"] is False


def test_sentiment_baseline():
    n = normalize_text
    assert score_text(n("Videonya bagus bangettt 😍"))[0] == "positive"
    assert score_text(n("gak bagus, jelek"))[0] == "negative"
    assert score_text(n("tidak jelek"))[0] == "positive"      # negation flips
    assert score_text(n("lagi makan siang"))[0] == "neutral"


def test_evaluate_requires_labels():
    assert evaluate(["", "x"], ["positive", "neutral"]) is None
    ev = evaluate(["positive", "negative"], ["positive", "positive"])
    assert ev["n_labeled"] == 2 and ev["accuracy"] == 0.5


def test_csv_full_flow(client):
    rows = ["comment,timestamp,video_id,username,label"]
    for i in range(30):
        rows.append(f"Cek link di bio ya diskon gede!! wa 0812345678{i % 10},2025-01-01 10:0{i % 3}:00,v1,user{i},neutral")
    rows += ["Videonya bagus banget,2025-01-01 12:00:00,v2,a,positive",
             "Jelek banget sampah,2025-01-02 12:00:00,v2,b,negative",
             "Aku suka konten ini sangat menghibur,2025-01-03 12:00:00,v1,c,positive",
             "Aku suka konten ini sangat menghibur!!!,2025-01-03 12:01:00,v2,d,positive",
             ",2025-01-03,v1,e,neutral"]
    r = upload(client, "\n".join(rows))
    assert r.status_code == 200, r.get_json()
    d = r.get_json()["data"]
    assert d["summary"]["total_comments"] == 34
    assert d["quality"]["empty_comments_removed"] == 1 and d["quality"]["username_column_ignored"]
    assert d["summary"]["promotional_signals"] >= 30
    assert d["promotional"]["disclaimer"]
    assert d["similarity"]["counts"]["comments_in_any_repeat"] >= 30
    assert d["sentiment"]["evaluation"]["n_labeled"] == 34
    assert d["coordination"]["time"] is not None
    assert "user0" not in str(d) and "08123456780" not in str(d)   # no usernames / raw phone numbers
    assert any(c["text"].find("[phone]") >= 0 for c in d["comments"])
    ids = {i["id"]: i for i in d["coordination"]["indicators"]}
    assert ids["cross_video"]["available"] and ids["repeated_text"]["strength"] in ("moderate", "strong")


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
    r = upload(client, "comment;timestamp\nhalo semua;2025-01-01\nbagus;2025-01-01;extra;cols\nmantap;x")
    d = r.get_json()["data"]
    assert r.status_code == 200 and d["quality"]["malformed_rows_skipped"] == 1
    assert d["quality"]["timestamps_unparseable"] >= 1
    assert d["coordination"]["time"] is None   # too few timestamps: no chart


def test_row_limit():
    class Small(__import__("config").Config):
        MAX_ROWS = 3
    c = create_app(Small).test_client()
    r = upload(c, "comment\na\nb\nc\nd")
    assert r.status_code == 413 and r.get_json()["error"]["code"] == "too_many_rows"


@pytest.mark.parametrize("url,valid,kind", [
    ("https://www.tiktok.com/@some.user/video/7234567890123456789?is_from_webapp=1", True, "video"),
    ("tiktok.com/@u/video/7234567890123456789", True, "video"),
    ("https://vm.tiktok.com/ZSabc12345/", True, "short_link"),
    ("https://www.tiktok.com/@user", False, None),
    ("https://evil-tiktok.com/@u/video/7234567890123456789", False, None),
    ("https://tiktok.com.evil.com/@u/video/7234567890123456789", False, None),
    ("javascript:alert(1)", False, None),
    ("https://user:pw@www.tiktok.com/@u/video/7234567890123456789", False, None),
    ("", False, None),
])
def test_url_validation(url, valid, kind):
    ok_, info = validate_tiktok_url(url)
    assert ok_ is valid
    if valid:
        assert info["url_type"] == kind and "?" not in info["normalized_url"]


def test_url_endpoint_is_honest(client):
    r = client.post("/api/analyze-url", json={"url": "https://www.tiktok.com/@u/video/7234567890123456789"})
    d = r.get_json()["data"]
    assert r.status_code == 200 and d["content_analyzed"] is False and d["comments_retrieved"] == 0
    assert d["integration"]["configured"] is False and d["analysis_status"] == "validated_only"
    assert client.post("/api/analyze-url", json={"url": "https://example.com"}).status_code == 422
    assert client.post("/api/analyze-url", data="nope").status_code == 400


def test_research_video_query_route(monkeypatch):
    class ResearchConfig(__import__("config").Config):
        TIKTOK_API_ACCESS_TOKEN = "test-token"

    calls = []

    def fake_query(config, query):
        calls.append((config, query))
        return {
            "videos": [{"id": "123", "like_count": 10, "view_count": 20,
                        "comment_count": 2, "share_count": 1}],
            "cursor": 100,
            "has_more": True,
        }

    monkeypatch.setattr(app_module, "query_public_videos", fake_query)
    test_client = create_app(ResearchConfig).test_client()
    payload = {
        "keyword": "hello world",
        "region_codes": ["us", "CA"],
        "start_date": "20261001",
        "end_date": "20261002",
        "max_count": 100,
    }

    response = test_client.post("/api/research/videos", json=payload)

    assert response.status_code == 200
    assert response.get_json()["data"]["videos"][0]["view_count"] == 20
    assert calls == [(ResearchConfig, {
        "keyword": "hello world",
        "region_codes": ["US", "CA"],
        "start_date": "20261001",
        "end_date": "20261002",
        "max_count": 100,
        "cursor": 0,
    })]


@pytest.mark.parametrize("payload", [
    {"keyword": "", "region_codes": ["US"], "start_date": "20261001", "end_date": "20261002"},
    {"keyword": "hello", "region_codes": ["USA"], "start_date": "20261001", "end_date": "20261002"},
    {"keyword": "hello", "region_codes": ["US"], "start_date": "20260230", "end_date": "20261002"},
    {"keyword": "hello", "region_codes": ["US"], "start_date": "20261003", "end_date": "20261002"},
    {"keyword": "hello", "region_codes": ["US"], "start_date": "20261001", "end_date": "20261002", "max_count": 101},
])
def test_research_video_query_rejects_invalid_input(payload):
    response = create_app().test_client().post("/api/research/videos", json=payload)
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_research_video_query_requires_token():
    response = create_app().test_client().post("/api/research/videos", json={
        "keyword": "hello",
        "region_codes": ["US", "CA"],
        "start_date": "20261001",
        "end_date": "20261002",
    })
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "research_api_not_configured"


def test_query_public_videos_builds_authorized_request(monkeypatch):
    class ResearchConfig(__import__("config").Config):
        TIKTOK_API_ACCESS_TOKEN = "private-test-token"

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"data": {"videos": [], "cursor": 0, "has_more": False}}).encode()

    def fake_urlopen(request, timeout):
        assert request.full_url == (
            "https://open.tiktokapis.com/v2/research/video/query/"
            "?fields=id%2Clike_count%2Cview_count%2Ccomment_count%2Cshare_count"
        )
        assert request.get_header("Authorization") == "Bearer private-test-token"
        assert timeout == 20
        body = json.loads(request.data)
        assert body["query"]["and"] == [
            {"operation": "IN", "field_name": "region_code", "field_values": ["US", "CA"]},
            {"operation": "EQ", "field_name": "keyword", "field_values": ["hello world"]},
        ]
        assert body["is_random"] is False
        return Response()

    monkeypatch.setattr("integrations.tiktok.urlopen", fake_urlopen)
    result = query_public_videos(ResearchConfig, {
        "keyword": "hello world",
        "region_codes": ["US", "CA"],
        "start_date": "20261001",
        "end_date": "20261002",
        "max_count": 100,
        "cursor": 0,
    })
    assert result == {"videos": [], "cursor": 0, "has_more": False}


def test_time_burst_is_detected_and_reported_in_utc(client):
    rows = ["comment,timestamp"]
    for i in range(30):   # background activity: one comment every 20 minutes
        rows.append(f"komentar biasa nomor {i} tentang video,2025-05-01 {8 + (i * 20) // 60:02d}:{(i * 20) % 60:02d}:00")
    for i in range(25):   # burst of 25 identical comments within five minutes
        rows.append(f"wajib nonton sampai habis luar biasa,2025-05-01 12:0{i % 5}:{i:02d}")
    d = upload(client, "\n".join(rows)).get_json()["data"]
    t = d["coordination"]["time"]
    assert max(p["count"] for p in t["series"]) >= 25, "chart series must contain the burst"
    assert t["bursts"] and t["bursts"][0]["comments"] >= 25
    assert t["bursts"][0]["share_also_repeated_text"] > 0.9
    assert t["first"].endswith("Z") and t["bursts"][0]["bucket_start"].endswith("Z")
    ind = {i["id"]: i for i in d["coordination"]["indicators"]}
    assert ind["time_concentration"]["strength"] in ("moderate", "strong")
