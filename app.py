from flask import Flask, request, jsonify
from flask_cors import CORS
from urllib.parse import urlparse
import re

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

COMMENT_CANDIDATES = [
    "comment",
    "comments",
    "text",
    "content",
    "comment_text",
    "komentar",
    "teks",
]
TIME_CANDIDATES = ["timestamp", "created_at", "comment_time", "date", "waktu", "tanggal"]
VIDEO_CANDIDATES = ["video_id", "video", "video_url", "id_video", "videoid"]

POSITIVE = {
    "bagus", "suka", "mantap", "keren", "terbaik", "recommended", "rekomendasi",
    "bermanfaat", "enak", "worth it", "percaya", "love", "great", "good", "hebat",
    "menarik", "cocok", "sangat bagus", "wow",
}
NEGATIVE = {
    "buruk", "jelek", "kecewa", "bohong", "mahal", "parah", "gagal",
    "menipu", "penipuan", "benci", "bad", "worst", "rugi", "zonk",
    "nggak bagus", "tidak bagus", "mengganggu", "kesal", "sakit hati",
}
PROMO = {
    "beli", "checkout", "diskon", "promo", "gratis ongkir", "kode voucher",
    "link di bio", "keranjang kuning", "gunakan kode", "harga spesial",
    "order sekarang", "affiliate", "endorse", "sponsored", "iklan", "dm untuk",
    "hubungi wa", "follow dan like", "link jualan", "gratis follow",
}


def find_column(df, candidates):
    lookup = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None


def normalize_text(value):
    text = str(value or "").lower()
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"[@#]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def lexicon_sentiment(text):
    normalized = normalize_text(text)
    if not normalized:
        return "unknown"

    pos = sum(1 for term in POSITIVE if term in normalized)
    neg = sum(1 for term in NEGATIVE if term in normalized)

    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def safe_records(df, limit=100):
    return df.head(limit).where(pd.notnull(df), None).to_dict(orient="records")


def is_supported_tiktok_url(url):
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host == "tiktok.com" or host.endswith(".tiktok.com"):
        return True
    return host in {"vm.tiktok.com", "vt.tiktok.com", "m.tiktok.com"}


def analyze_dataframe(df):
    if df is None or df.empty:
        raise ValueError("The uploaded CSV has no rows to analyze.")

    comment_col = find_column(df, COMMENT_CANDIDATES)
    if comment_col is None:
        raise ValueError(
            "No comment column was found. Use a column named comment, comments, text, content, "
            "comment_text, komentar, or teks."
        )

    working = pd.DataFrame({"comment": df[comment_col].fillna("").astype(str).str.strip()})
    working = working[working["comment"] != ""].copy()
    if working.empty:
        raise ValueError("No non-empty comment text was found in the uploaded CSV.")

    time_col = find_column(df, TIME_CANDIDATES)
    if time_col:
        working["timestamp"] = pd.to_datetime(df.loc[working.index, time_col], errors="coerce", utc=True)
    else:
        working["timestamp"] = pd.NaT

    video_col = find_column(df, VIDEO_CANDIDATES)
    if video_col:
        working["video_id"] = df.loc[working.index, video_col].fillna("").astype(str)
    else:
        working["video_id"] = ""

    working["normalized"] = working["comment"].map(normalize_text)
    working["sentiment"] = working["comment"].map(lexicon_sentiment)
    working["is_promotional"] = working["normalized"].map(
        lambda s: any(term in s for term in PROMO)
    )

    total = len(working)
    sentiment_counts = working["sentiment"].value_counts().to_dict()
    sentiment = {
        "positive": int(sentiment_counts.get("positive", 0)),
        "neutral": int(sentiment_counts.get("neutral", 0)),
        "negative": int(sentiment_counts.get("negative", 0)),
        "unknown": int(sentiment_counts.get("unknown", 0)),
    }

    nonempty = working[working["normalized"] != ""]
    duplicate_groups = nonempty.groupby("normalized").size().sort_values(ascending=False)
    repeated_groups = [
        {"normalized_text": text, "count": int(count)}
        for text, count in duplicate_groups.items()
        if count > 1
    ][:10]
    repeated_unique_texts = len(repeated_groups)

    texts = working["normalized"].tolist()
    similar_pairs = []
    sample_limit = min(len(texts), 300)
    sample_texts = texts[:sample_limit]
    if sample_limit >= 2 and len(set(t for t in sample_texts if t)) >= 2:
        try:
            matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(sample_texts)
            similarity = cosine_similarity(matrix, dense_output=True)
            for i in range(sample_limit):
                for j in range(i + 1, sample_limit):
                    if similarity[i, j] >= 0.82 and sample_texts[i] != sample_texts[j]:
                        similar_pairs.append({
                            "comment_a": str(working.iloc[i]["comment"])[:240],
                            "comment_b": str(working.iloc[j]["comment"])[:240],
                            "similarity": round(float(similarity[i, j]), 3),
                        })
                        if len(similar_pairs) >= 20:
                            break
                if len(similar_pairs) >= 20:
                    break
        except ValueError:
            pass

    timed = working.dropna(subset=["timestamp"]).copy()
    hourly = []
    if not timed.empty:
        timed["hour"] = timed["timestamp"].dt.floor("h")
        counts = timed.groupby("hour").size().sort_index()
        hourly = [{"time": timestamp.isoformat(), "count": int(count)} for timestamp, count in counts.items()]

    promo_count = int(working["is_promotional"].sum())
    valid_timestamps = int(working["timestamp"].notna().sum())
    video_count = int(working.loc[working["video_id"] != "", "video_id"].nunique())

    findings = []
    if repeated_unique_texts:
        findings.append({
            "title": "Repeated text detected",
            "detail": f"{repeated_unique_texts} repeated text groups were found after normalization.",
            "severity": "review",
            "evidence_count": repeated_unique_texts,
        })
    if similar_pairs:
        findings.append({
            "title": "Highly similar comment pairs",
            "detail": f"Up to {len(similar_pairs)} pairs reached a TF-IDF cosine similarity threshold of 0.82 in the sampled data.",
            "severity": "review",
            "evidence_count": len(similar_pairs),
        })
    if promo_count:
        findings.append({
            "title": "Promotional language detected",
            "detail": f"{promo_count} comments matched promotional keywords or phrases in the baseline detector.",
            "severity": "info",
            "evidence_count": promo_count,
        })
    if valid_timestamps == 0:
        findings.append({
            "title": "Timestamps unavailable",
            "detail": "No valid timestamps were present, so time-based patterns could not be evaluated.",
            "severity": "limitation",
            "evidence_count": 0,
        })
    if video_count < 2:
        findings.append({
            "title": "Limited cross-video context",
            "detail": "Fewer than two unique video IDs were present, so cross-video patterns are limited.",
            "severity": "limitation",
            "evidence_count": video_count,
        })

    coordination_signals = []
    if repeated_unique_texts:
        coordination_signals.append({
            "type": "repeated_comment_text",
            "status": "potential",
            "detail": "Repeated normalized comment text may reflect copy-paste behavior, spam, trends, or collaborative posting.",
            "evidence_count": repeated_unique_texts,
        })
    if similar_pairs:
        coordination_signals.append({
            "type": "similar_comment_similarity",
            "status": "potential",
            "detail": "High text similarity suggests coordinated wording patterns but is not proof of malicious coordination.",
            "evidence_count": len(similar_pairs),
        })
    if valid_timestamps:
        coordination_signals.append({
            "type": "posting_time_clustering",
            "status": "potential",
            "detail": "If comment timestamps are concentrated in narrow bursts, the pattern may warrant review as a coordination signal.",
            "evidence_count": valid_timestamps,
        })

    return {
        "source": "uploaded_csv",
        "analysis_status": "completed",
        "summary": {
            "total_comments": total,
            "positive": sentiment["positive"],
            "neutral": sentiment["neutral"],
            "negative": sentiment["negative"],
            "unknown_sentiment": sentiment["unknown"],
            "promotional_comments": promo_count,
            "repeated_text_groups": repeated_unique_texts,
            "similar_pairs": len(similar_pairs),
            "timestamps_available": valid_timestamps,
            "unique_videos": video_count,
        },
        "sentiment": sentiment,
        "repeated_comments": repeated_groups,
        "similar_pairs": similar_pairs,
        "hourly_activity": hourly,
        "coordination_signals": coordination_signals,
        "findings": findings,
        "examples": safe_records(
            working[["comment", "sentiment", "is_promotional"]].rename(
                columns={"is_promotional": "promotional_language_detected"}
            ),
            100,
        ),
        "method_notes": [
            "The sentiment detector uses a transparent lexicon baseline for Indonesian and English terms, not a validated trained model.",
            "Repeated or similar wording can come from memes, trends, copy-paste behavior, spam, or coordinated activity; it is not proof of coordinated behavior by itself.",
            "Promotional detection is keyword-based and best interpreted as a risk signal rather than confirmed advertising.",
            "Only comment text and available metadata from the uploaded dataset are used here."
        ],
        "data_quality": {
            "missing_timestamp_rows": int(working["timestamp"].isna().sum()),
            "empty_comment_rows": int(working["comment"].eq("").sum()),
            "unique_video_ids": video_count,
        },
    }


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "SocialScope AI API"})


@app.post("/api/analyze-csv")
def analyze_csv():
    if "file" not in request.files:
        return jsonify({"error": "Please upload a CSV file before running analysis."}), 400

    file = request.files["file"]
    if not file or not file.filename or not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "The uploaded file must be a CSV file."}), 400

    try:
        df = pd.read_csv(file, encoding="utf-8-sig")
        result = analyze_dataframe(df)
        return jsonify(result)
    except UnicodeDecodeError:
        return jsonify({"error": "The CSV cannot be decoded. Please save it as UTF-8 and retry."}), 400
    except pd.errors.EmptyDataError:
        return jsonify({"error": "The uploaded CSV file is empty."}), 400
    except pd.errors.ParserError:
        return jsonify({"error": "The CSV is malformed or contains inconsistent delimiters."}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Unexpected CSV analysis error")
        return jsonify({"error": "An unexpected error occurred while processing the CSV."}), 500


@app.post("/api/analyze-url")
def analyze_url():
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    if not url:
        return jsonify({"error": "Please provide a TikTok URL."}), 400
    if not re.match(r"^https?://", url, re.I):
        return jsonify({"error": "The URL must begin with http:// or https://."}), 400

    hostname = (urlparse(url).hostname or "").lower()
    if not is_supported_tiktok_url(url):
        return jsonify({"error": "This MVP only accepts TikTok domains and does not support other websites."}), 400

    return jsonify({
        "status": "validation_only",
        "source": "url_only",
        "analysis_status": "not_analyzed",
        "url": url,
        "is_valid_url": True,
        "authorized_api_configured": False,
        "message": "The URL format is valid, but the content has not been analyzed because no approved TikTok API or data connector is configured.",
        "next_steps": [
            "Upload a CSV of comment data that you are authorized to analyze.",
            "Connect an approved TikTok data source only after API permissions and compliance requirements are confirmed."
        ],
        "method_notes": [
            "This endpoint validates format and domain only. It does not scrape content or pretend that comments were retrieved without a configured integration.",
            "Automatic analysis requires an approved TikTok connector and access permissions."
        ],
    }), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
