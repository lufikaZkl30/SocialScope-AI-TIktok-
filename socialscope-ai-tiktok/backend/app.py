"""SocialScope AI - Flask API (independent, unofficial educational project; not a TikTok product)."""
import logging
import re
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from analysis import promo, sentiment
from analysis.errors import AnalysisError
from analysis.pipeline import LIMITATIONS, analyze_csv
from config import Config
from integrations.tiktok import (
    TikTokResearchApiError,
    get_connector,
    query_public_videos,
    research_api_status,
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

# Create the Flask app
def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)
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
                       "tiktok_research_api": research_api_status(config),
                   },
                   "limits": {"max_upload_mb": config.MAX_UPLOAD_MB, "max_rows": config.MAX_ROWS}})

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

    @app.post("/api/research/videos")
    def research_videos_route():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return fail("invalid_request", "Send the video query as a JSON object.", 400)

        keyword = payload.get("keyword")
        if not isinstance(keyword, str) or not keyword.strip() or len(keyword.strip()) > 200:
            return fail("invalid_parameter", "keyword must contain 1-200 characters.", 400)

        region_codes = payload.get("region_codes")
        if (not isinstance(region_codes, list) or not 1 <= len(region_codes) <= 10
                or any(not isinstance(code, str) or not re.fullmatch(r"[A-Za-z]{2}", code.strip())
                       for code in region_codes)):
            return fail("invalid_parameter", "region_codes must be a list of 1-10 two-letter country codes.", 400)
        region_codes = list(dict.fromkeys(code.strip().upper() for code in region_codes))

        dates = {}
        for field in ("start_date", "end_date"):
            value = payload.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"\d{8}", value):
                return fail("invalid_parameter", f"{field} must use YYYYMMDD format.", 400)
            try:
                datetime.strptime(value, "%Y%m%d")
            except ValueError:
                return fail("invalid_parameter", f"{field} is not a valid calendar date.", 400)
            dates[field] = value
        if dates["start_date"] > dates["end_date"]:
            return fail("invalid_parameter", "start_date must be on or before end_date.", 400)

        max_count = payload.get("max_count", 100)
        cursor = payload.get("cursor", 0)
        if isinstance(max_count, bool) or not isinstance(max_count, int) or not 1 <= max_count <= 100:
            return fail("invalid_parameter", "max_count must be an integer from 1 to 100.", 400)
        if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
            return fail("invalid_parameter", "cursor must be a non-negative integer.", 400)

        query = {
            "keyword": keyword.strip(),
            "region_codes": region_codes,
            **dates,
            "max_count": max_count,
            "cursor": cursor,
        }
        try:
            result = query_public_videos(config, query)
        except TikTokResearchApiError as e:
            return fail(e.code, e.message, e.status, e.details)
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
