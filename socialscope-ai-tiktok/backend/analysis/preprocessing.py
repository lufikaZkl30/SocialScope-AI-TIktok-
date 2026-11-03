"""CSV loading, validation and text normalization.

Two text forms are used:
  * display text - original wording with personal identifiers masked (shown/exported)
  * norm text    - lowercase, URLs removed, slang expanded, letters de-stretched
                   (used for sentiment and similarity). Meaning-bearing words are kept.
"""
import csv
import io
import re
import unicodedata

import pandas as pd

from .errors import AnalysisError

COLUMN_ALIASES = {
    "comment": ["comment", "comments", "comment_text", "text", "komentar", "content"],
    "timestamp": ["timestamp", "time", "created_at", "create_time", "date", "datetime", "waktu", "tanggal"],
    "video_id": ["video_id", "videoid", "video", "aweme_id"],
    "label": ["label", "sentiment_label", "true_label", "gold_label"],
    # Detected only so we can say it was ignored. Never analysed, returned or exported.
    "username": ["username", "user", "author", "user_name", "unique_id"],
}

SLANG = {
    "bgt": "banget", "bngt": "banget", "bgd": "banget", "gk": "gak", "ga": "gak", "gx": "gak",
    "nggak": "gak", "ngga": "gak", "enggak": "gak", "engga": "gak", "tdk": "tidak", "tak": "tidak",
    "yg": "yang", "dgn": "dengan", "dg": "dengan", "jg": "juga", "jga": "juga", "udh": "sudah",
    "udah": "sudah", "sdh": "sudah", "blm": "belum", "krn": "karena", "karna": "karena",
    "utk": "untuk", "sy": "saya", "gue": "saya", "gw": "saya", "klo": "kalau", "kalo": "kalau",
    "emg": "memang", "emang": "memang", "trs": "terus", "trus": "terus", "bs": "bisa",
    "bkn": "bukan", "dr": "dari", "mantul": "mantap", "mantab": "mantap", "kereen": "keren",
    "bgus": "bagus", "tq": "terima kasih", "thanks": "terima kasih", "makasih": "terima kasih",
    "thx": "terima kasih", "pake": "pakai", "pakek": "pakai", "bener": "benar", "betul": "benar",
    "ngeselin": "menyebalkan", "nyebelin": "menyebalkan", "males": "malas", "bosen": "bosan",
    "hoax": "hoaks", "penipuan": "penipu", "rekomen": "rekomendasi", "recommended": "rekomendasi",
    "folback": "follow back", "follback": "follow back",
}

URL_RE = re.compile(r"(https?://\S+|www\.\S+|\b[\w-]+\.(?:com|id|co|net|me|link|shop|xyz)(?:/\S*)?\b)", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
MENTION_RE = re.compile(r"(?<![\w.])@[\w.]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?62|0)8[\d\s().-]{7,14}\d(?!\d)")
STRETCH_RE = re.compile(r"(.)\1{2,}")


def mask_pii(text: str) -> str:
    """Mask emails, phone numbers and @mentions for display and export."""
    text = EMAIL_RE.sub("[email]", text)
    text = PHONE_RE.sub("[phone]", text)
    return MENTION_RE.sub("@user", text)


def normalize_text(text: str) -> str:
    """Normalize for analysis while keeping meaning-bearing tokens and emoji."""
    text = unicodedata.normalize("NFKC", str(text)).lower()
    text = EMAIL_RE.sub(" ", text)
    text = PHONE_RE.sub(" ", text)  # phone numbers never enter analysis outputs
    text = URL_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    text = STRETCH_RE.sub(r"\1", text)  # "baguuuus" -> "bagus"
    out = []
    for tok in re.findall(r"[\w']+|[^\w\s]", text):
        if tok[0].isalnum() or tok[0] in "_'":
            out.append(SLANG.get(tok, tok))
        elif unicodedata.category(tok) == "So":  # keep emoji/symbols; drop punctuation
            out.append(tok)
    return " ".join(out)


def _read_csv_text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    raise AnalysisError("Could not decode the file. Save it as UTF-8 CSV and try again.", "bad_encoding")


def _find_column(columns, key):
    lowered = {str(c).strip().lower().replace(" ", "_"): c for c in columns}
    for alias in COLUMN_ALIASES[key]:
        if alias in lowered:
            return lowered[alias]
    return None


def _parse_timestamps(series: pd.Series) -> pd.Series:
    s = series.astype("string").str.strip()
    numeric = pd.to_numeric(s, errors="coerce")
    if numeric.notna().mean() > 0.8:  # unix seconds or milliseconds
        unit = "ms" if numeric.dropna().abs().median() > 1e11 else "s"
        return pd.to_datetime(numeric, unit=unit, errors="coerce", utc=True)
    return pd.to_datetime(s, errors="coerce", utc=True, format="mixed")


def load_comments(raw: bytes, max_rows: int):
    """Parse and validate CSV bytes. Returns (DataFrame, quality dict)."""
    if not raw or not raw.strip():
        raise AnalysisError("The file is empty.", "empty_file")
    text = _read_csv_text(raw)
    header = text.lstrip().split("\n", 1)[0]
    sep = max(",;\t|", key=lambda d: header.count(d)) if any(d in header for d in ",;\t|") else ","
    reader = csv.reader(io.StringIO(text), delimiter=sep)
    records, row_nums, malformed = [], [], 0
    try:
        header = [h.strip() for h in next(reader)]
        for n, rec in enumerate(reader, start=2):  # n = record number; the header is record 1
            if not any(c.strip() for c in rec):
                continue  # blank line
            if len(rec) > len(header):  # e.g. an unquoted comma inside a comment: skip, never truncate
                malformed += 1
                continue
            records.append(rec + [""] * (len(header) - len(rec)))
            row_nums.append(n)
    except (csv.Error, StopIteration) as exc:
        raise AnalysisError(f"The file could not be parsed as CSV: {exc}", "malformed_csv") from exc
    df = pd.DataFrame(records, columns=header, dtype=str)
    comment_col = _find_column(df.columns, "comment")
    if comment_col is None:
        raise AnalysisError(
            "Required column not found. Add a column named 'comment' (also accepted: text, komentar).",
            "missing_column", details={"found_columns": [str(c) for c in df.columns][:30]})
    if df.empty:
        raise AnalysisError("The file has a header but no data rows.", "no_rows")

    ts_col, vid_col = _find_column(df.columns, "timestamp"), _find_column(df.columns, "video_id")
    label_col, user_col = _find_column(df.columns, "label"), _find_column(df.columns, "username")

    work = pd.DataFrame({"row": row_nums})  # record number; the header row is 1
    work["raw"] = df[comment_col].astype(str).str.strip().values
    work["timestamp"] = _parse_timestamps(df[ts_col]).values if ts_col else pd.NaT
    work["video_id"] = (df[vid_col].astype(str).str.strip().replace("", pd.NA).values
                        if vid_col else pd.NA)
    work["label"] = df[label_col].astype(str).str.strip().str.lower().values if label_col else None
    rows_received = len(work)

    empty_mask = work["raw"].eq("") | work["raw"].str.lower().isin(["nan", "null", "none"])
    work = work[~empty_mask].reset_index(drop=True)
    if work.empty:
        raise AnalysisError("Every row has an empty comment value.", "no_valid_comments")
    if len(work) > max_rows:
        raise AnalysisError(
            f"The file has {len(work)} usable comments; the limit is {max_rows}. "
            "Split the file or raise MAX_ROWS in backend/.env.", "too_many_rows", 413)

    work["display"] = work["raw"].map(mask_pii).str.slice(0, 500)
    work["norm"] = work["raw"].map(normalize_text)

    quality = {
        "rows_received": rows_received,
        "rows_analyzed": int(len(work)),
        "empty_comments_removed": int(empty_mask.sum()),
        "malformed_rows_skipped": malformed,
        "columns_detected": {"comment": str(comment_col),
                             "timestamp": str(ts_col) if ts_col else None,
                             "video_id": str(vid_col) if vid_col else None,
                             "label": str(label_col) if label_col else None},
        "username_column_ignored": user_col is not None,
        "timestamps_parsed": int(work["timestamp"].notna().sum()) if ts_col else 0,
        "timestamps_unparseable": int(work["timestamp"].isna().sum()) if ts_col else 0,
        "video_ids_present": int(work["video_id"].notna().sum()) if vid_col else 0,
        "distinct_video_ids": int(work["video_id"].nunique()) if vid_col else 0,
        "very_short_comments": int((work["norm"].str.split().str.len() < 2).sum()),
        "delimiter": sep,
    }
    return work, quality
