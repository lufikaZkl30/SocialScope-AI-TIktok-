"""SocialScope AI - Flask API (independent, unofficial educational project; not a TikTok product)."""
import logging
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

from flask import Flask, jsonify, redirect, request, session
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from analysis import promo, sentiment
from analysis.errors import AnalysisError
from analysis.pipeline import LIMITATIONS, analyze_csv
from config import Config
from integrations.tiktok import (
    TikTokApiError,
    build_authorization_url,
    clear_account_tokens,
    exchange_authorization_code,
    get_account_videos,
    get_connector,
    login_kit_status,
    store_account_tokens,
    validate_tiktok_url,
)

log = logging.getLogger("socialscope")


def ok(data, status=200):
    return jsonify({"ok": True, "data": data}), status


def fail(code, message, status, details=None):
    body = {"ok": False, "error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def _tiktok_frontend_redirect(config, status, reason=None):
    query = {"tiktok": status}
    if reason:
        query["reason"] = reason
    return redirect(f"{config.TIKTOK_FRONTEND_URL.rstrip('/')}?{urlencode(query)}")

# Create the Flask app
def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=getattr(config, "SESSION_COOKIE_SECURE", False),
    )
    CORS(app, resources={r"/api/*": {"origins": config.CORS_ORIGINS}})
    keywords = promo.load_keywords(config.PROMO_KEYWORDS_PATH)
    patterns = promo.compile_patterns(keywords)
    connector = get_connector(config)

    @app.get("/api/health")
    def health():
        return ok({"status": "healthy", "service": "SocialScope AI API", "version": config.VERSION,
                   "time": datetime.now(timezone.utc).isoformat(),
                   "integrations": {
                       "tiktok_api": connector.status(),
                       "tiktok_account": login_kit_status(config, session.get("tiktok_session_id")),
                   },
                   "limits": {"max_upload_mb": config.MAX_UPLOAD_MB, "max_rows": config.MAX_ROWS}})

    @app.get("/api/tiktok/status")
    def tiktok_status():
        return ok(login_kit_status(config, session.get("tiktok_session_id")))

    @app.get("/api/tiktok/login")
    def tiktok_login():
        state = secrets.token_urlsafe(32)
        session["tiktok_oauth_state"] = state
        try:
            return redirect(build_authorization_url(config, state))
        except TikTokApiError as e:
            return fail(e.code, e.message, e.status, e.details)

    @app.get("/api/tiktok/callback")
    def tiktok_callback():
        expected_state = session.pop("tiktok_oauth_state", None)
        received_state = request.args.get("state", "")
        if not expected_state or not secrets.compare_digest(expected_state, received_state):
            return _tiktok_frontend_redirect(config, "error", "invalid_state")
        if request.args.get("error"):
            return _tiktok_frontend_redirect(config, "error", "authorization_denied")
        code = request.args.get("code", "")
        if not code:
            return _tiktok_frontend_redirect(config, "error", "missing_authorization_code")
        try:
            tokens = exchange_authorization_code(config, code)
        except TikTokApiError:
            return _tiktok_frontend_redirect(config, "error", "token_exchange_failed")

        session_id = secrets.token_urlsafe(32)
        store_account_tokens(session_id, tokens)
        session["tiktok_session_id"] = session_id
        return _tiktok_frontend_redirect(config, "connected")

    @app.post("/api/tiktok/disconnect")
    def tiktok_disconnect():
        session_id = session.pop("tiktok_session_id", None)
        if session_id:
            clear_account_tokens(session_id)
        return ok({"connected": False})

    @app.post("/api/tiktok/videos")
    def tiktok_videos():
        payload = request.get_json(silent=True)
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return fail("invalid_request", "Send the video-list options as a JSON object.", 400)
        cursor = payload.get("cursor", 0)
        max_count = payload.get("max_count", 20)
        if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
            return fail("invalid_parameter", "cursor must be a non-negative integer.", 400)
        if isinstance(max_count, bool) or not isinstance(max_count, int) or not 1 <= max_count <= 20:
            return fail("invalid_parameter", "max_count must be an integer from 1 to 20.", 400)
        try:
            videos = get_account_videos(
                config, session.get("tiktok_session_id"), cursor=cursor, max_count=max_count
            )
        except TikTokApiError as e:
            return fail(e.code, e.message, e.status, e.details)
        return ok(videos)

    @app.get("/api/methodology")
    def methodology():
        return ok({"sentiment": sentiment.METHOD,
                   "promotional_categories": {k: {"label": promo.CATEGORY_LABELS.get(k, k), "keywords": v}
                                              for k, v in keywords.items()},
                   "similarity": {"method": "TF-IDF (character 3-5 grams) + cosine similarity",
                                  "default_threshold": config.SIMILARITY_THRESHOLD},
                   "limitations": LIMITATIONS})

    @app.post("/api/analyze-csv")
    def analyze_csv_route():
        f = request.files.get("file")
        if f is None or not f.filename:
            return fail("missing_file", "Attach a CSV file in the 'file' form field.", 400)
        if not f.filename.lower().endswith(".csv"):
            return fail("unsupported_format", "Only .csv files are supported.", 415)
        try:
            threshold = float(request.form.get("similarity_threshold", config.SIMILARITY_THRESHOLD))
        except ValueError:
            return fail("invalid_parameter", "similarity_threshold must be a number.", 400)
        if not 0.5 <= threshold <= 0.99:
            return fail("invalid_parameter", "similarity_threshold must be between 0.50 and 0.99.", 400)
        result = analyze_csv(f.read(), f.filename[:120], config, patterns, threshold)
        return ok(result)

# post endpoint to validate TikTok URL format and return analysis status
    @app.post("/api/analyze-url")
    def analyze_url_route():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or "url" not in payload:
            return fail("invalid_request", "Send JSON like {\"url\": \"https://www.tiktok.com/@user/video/123...\"}.", 400)
        valid, info = validate_tiktok_url(str(payload["url"]))
        if not valid:
            return fail("invalid_url", info["reason"], 422)
        integration = connector.status()
        return ok({
            "analysis_status": "validated_only",
            "url_valid": True,
            "content_analyzed": False,
            "comments_retrieved": 0,
            "url": info,
            "integration": integration,
            "message": ("The URL format is valid, but no comments were retrieved or analysed. "
                        + integration["message"]),
            "next_step": "Upload a CSV of comments on the Comment Analysis page to run the analysis.",
        })

    @app.errorhandler(AnalysisError)
    def on_analysis_error(e):
        return fail(e.code, e.message, e.status, e.details)

    @app.errorhandler(HTTPException)
    def on_http_error(e):
        codes = {404: "not_found", 405: "method_not_allowed", 413: "file_too_large"}
        msg = (f"The file exceeds the {config.MAX_UPLOAD_MB} MB upload limit." if e.code == 413 else e.description)
        return fail(codes.get(e.code, "http_error"), msg, e.code or 500)

    @app.errorhandler(Exception)
    def on_unexpected(e):
        log.exception("Unhandled error")
        return fail("internal_error", "Something went wrong while analysing the data. Check the server log.", 500)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=Config.PORT, debug=Config.DEBUG)
