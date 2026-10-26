from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import re
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173"]}})
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

COMMENT_CANDIDATES = ["comment", "comments", "text", "content", "komentar", "teks"]
TIME_CANDIDATES = ["timestamp", "created_at", "comment_time", "date", "waktu", "tanggal"]
VIDEO_CANDIDATES = ["video_id", "video", "video_url", "id_video"]

POSITIVE = {
    "bagus", "suka", "mantap", "keren", "terbaik", "recommended", "rekomendasi",
    "bermanfaat", "enak", "worth it", "percaya", "love", "great", "good", "hebat"
}
NEGATIVE = {
    "buruk", "jelek", "kecewa", "bohong", "mahal", "parah", "buruk", "gagal",
    "menipu", "penipuan", "benci", "bad", "worst", "rugi", "zonk"
}
PROMO = {
    "beli", "checkout", "diskon", "promo", "gratis ongkir", "kode voucher",
    "link di bio", "keranjang kuning", "gunakan kode", "harga spesial",
    "order sekarang", "affiliate", "endorse", "sponsored", "iklan"
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
    return re.sub(r"\s+", " ", text).strip()

def lexicon_sentiment(text):
    normalized = normalize_text(text)
    if not normalized:
        return "unknown"
    # Phrase matching first, then token matching. This is a transparent baseline,
    # not a trained or validated Indonesian sentiment model.
    pos = sum(1 for term in POSITIVE if term in normalized)
    neg = sum(1 for term in NEGATIVE if term in normalized)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    if pos == 0 and neg == 0:
        return "neutral"
    return "neutral"

def safe_records(df, limit=100):
    return df.head(limit).where(pd.notnull(df), None).to_dict(orient="records")

def analyze_dataframe(df):
    if df.empty:
        raise ValueError("CSV tidak memiliki baris data.")

    comment_col = find_column(df, COMMENT_CANDIDATES)
    if comment_col is None:
        raise ValueError(
            "Kolom komentar tidak ditemukan. Gunakan salah satu nama kolom: "
            "comment, comments, text, content, komentar, atau teks."
        )

    working = pd.DataFrame()
    working["comment"] = df[comment_col].fillna("").astype(str).str.strip()
    working = working[working["comment"] != ""].copy()
    if working.empty:
        raise ValueError("Tidak ada komentar berisi teks yang dapat dianalisis.")

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

    # Exact duplicate detection after normalization.
    nonempty = working[working["normalized"] != ""]
    duplicate_groups = nonempty.groupby("normalized").size().sort_values(ascending=False)
    repeated_groups = [
        {"normalized_text": text, "count": int(count)}
        for text, count in duplicate_groups.items() if count > 1
    ][:10]
    repeated_comment_count = int(sum(group["count"] for group in repeated_groups))
    repeated_unique_texts = len(repeated_groups)

    # TF-IDF cosine similarity: a small sample keeps work bounded for an MVP.
    # This is similarity, not proof of coordination.
    texts = working["normalized"].tolist()
    similar_pairs = []
    sample_limit = min(len(texts), 300)
    sample_texts = texts[:sample_limit]
    if len(set(t for t in sample_texts if t)) >= 2:
        try:
            matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(sample_texts)
            sim = cosine_similarity(matrix, dense_output=True)
            for i in range(sample_limit):
                for j in range(i + 1, sample_limit):
                    if sim[i, j] >= 0.82 and sample_texts[i] != sample_texts[j]:
                        similar_pairs.append({
                            "comment_a": working.iloc[i]["comment"][:240],
                            "comment_b": working.iloc[j]["comment"][:240],
                            "similarity": round(float(sim[i, j]), 3)
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
        hourly = [{"time": t.isoformat(), "count": int(c)} for t, c in counts.items()]

    promo_count = int(working["is_promotional"].sum())
    valid_timestamps = int(working["timestamp"].notna().sum())
    video_count = int(working.loc[working["video_id"] != "", "video_id"].nunique())

    findings = []
    if repeated_unique_texts:
        findings.append({
            "title": "Komentar identik ditemukan",
            "detail": f"{repeated_unique_texts} teks komentar berulang ditemukan setelah normalisasi.",
            "severity": "review",
            "evidence_count": repeated_unique_texts
        })
    if similar_pairs:
        findings.append({
            "title": "Komentar dengan teks mirip",
            "detail": f"Ditemukan hingga {len(similar_pairs)} pasangan komentar dengan cosine similarity ≥ 0,82 pada sampel maksimal 300 komentar.",
            "severity": "review",
            "evidence_count": len(similar_pairs)
        })
    if promo_count:
        findings.append({
            "title": "Bahasa promosi terdeteksi",
            "detail": f"{promo_count} komentar memuat satu atau lebih istilah promosi dari daftar kata sederhana.",
            "severity": "info",
            "evidence_count": promo_count
        })
    if valid_timestamps == 0:
        findings.append({
            "title": "Analisis waktu tidak tersedia",
            "detail": "Tidak ada timestamp yang valid. Pola waktu dan lonjakan komentar tidak dapat dinilai.",
            "severity": "limitation",
            "evidence_count": 0
        })
    if video_count < 2:
        findings.append({
            "title": "Data lintas video terbatas",
            "detail": "Kurang dari dua ID video unik tersedia. Koordinasi lintas video tidak dapat dievaluasi.",
            "severity": "limitation",
            "evidence_count": video_count
        })

    return {
        "source": "uploaded_csv",
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
            "unique_videos": video_count
        },
        "sentiment": sentiment,
        "repeated_comments": repeated_groups,
        "similar_pairs": similar_pairs,
        "hourly_activity": hourly,
        "findings": findings,
        "examples": safe_records(working[["comment", "sentiment", "is_promotional"]].rename(
            columns={"is_promotional": "promotional_language_detected"}
        ), 100),
        "method_notes": [
            "Sentimen memakai kamus kata sederhana; bukan model sentimen terlatih dan belum tervalidasi.",
            "Kemiripan teks dan komentar berulang bukan bukti bahwa akun dikoordinasikan.",
            "Deteksi promosi berbasis daftar kata; hasil dapat salah untuk sarkasme, slang, atau konteks.",
            "Analisis hanya mencakup baris dan kolom yang ada di CSV."
        ]
    }

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "TikTok Pulse API"})

@app.post("/api/analyze-csv")
def analyze_csv():
    if "file" not in request.files:
        return jsonify({"error": "Pilih file CSV terlebih dahulu."}), 400
    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Format file harus CSV."}), 400
    try:
        df = pd.read_csv(file, encoding="utf-8-sig")
        result = analyze_dataframe(df)
        return jsonify(result)
    except UnicodeDecodeError:
        return jsonify({"error": "Encoding CSV tidak terbaca. Simpan ulang sebagai CSV UTF-8."}), 400
    except pd.errors.ParserError:
        return jsonify({"error": "CSV tidak valid atau pemisah kolom tidak konsisten."}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Unexpected CSV analysis error")
        return jsonify({"error": "Terjadi kesalahan saat memproses CSV. Periksa format file dan coba lagi."}), 500

@app.post("/api/analyze-url")
def analyze_url():
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    if not url:
        return jsonify({"error": "Masukkan URL TikTok."}), 400
    if not re.match(r"^https?://", url, re.I):
        return jsonify({"error": "URL harus dimulai dengan http:// atau https://."}), 400
    # Deliberately no scraping and no fabricated results. This endpoint only reports
    # current capability until an approved TikTok connector is configured.
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    allowed = host == "tiktok.com" or host.endswith(".tiktok.com")
    if not allowed:
        return jsonify({"error": "Untuk MVP ini, URL harus berasal dari domain TikTok."}), 400
    return jsonify({
        "status": "data_unavailable",
        "source": "url_only",
        "url": url,
        "message": "URL valid, tetapi backend belum memiliki konektor TikTok yang terotorisasi untuk mengambil komentar atau metadata. Tidak ada analisis yang dijalankan.",
        "next_steps": [
            "Unggah CSV komentar yang boleh digunakan untuk dianalisis.",
            "Tambahkan konektor API TikTok resmi setelah akses dan izin dikonfirmasi."
        ]
    }), 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
