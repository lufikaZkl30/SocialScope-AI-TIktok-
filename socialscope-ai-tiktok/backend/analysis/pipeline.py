"""Orchestrates the full CSV analysis and builds the JSON payload for the API."""
from datetime import datetime, timezone

from . import promo, sentiment
from .coordination import analyze_coordination
from .preprocessing import load_comments
from .similarity import analyze_similarity

LIMITATIONS = [
    "Sentiment comes from a rule-based lexicon baseline, not a trained model; sarcasm, slang gaps and context are missed.",
    "No accuracy figure is claimed. Accuracy is reported only when the CSV contains your own 'label' column.",
    "Promotional flags are keyword and pattern signals. They do not prove paid advertising.",
    "Similar or repeated comments can be ordinary trends or catchphrases. They do not identify bots or buzzers.",
    "Coordination indicators are exploratory statistics on this one file and are not proof of coordinated behaviour.",
    "Results describe only the uploaded rows, which may not represent all comments on a video.",
]


def _pct(n, total):
    return round(100 * n / total, 1) if total else 0.0


def analyze_csv(raw: bytes, filename: str, config, promo_patterns, threshold=None):
    threshold = threshold or config.SIMILARITY_THRESHOLD
    df, quality = load_comments(raw, config.MAX_ROWS)
    n = len(df)

    results, counts = sentiment.analyze_sentiment(df["norm"])
    evaluation = (sentiment.evaluate(df["label"], [r[0] for r in results])
                  if quality["columns_detected"]["label"] else None)
    promos = [promo.detect(t, promo_patterns) for t in df["raw"]]
    sim = analyze_similarity(df, threshold)
    coord = analyze_coordination(df, sim, quality)

    comments = []
    for i, row in df.iterrows():
        label, score, terms = results[i]
        p = promos[i]
        comments.append({
            "row": int(row["row"]), "text": row["display"], "sentiment": label, "score": score,
            "matched_terms": terms[:6],
            "promo_signal": p["strength"] if p else None, "promo_reason": p["reason"] if p else None,
            "duplicate_group": sim["_dup_member"].get(i), "similar_group": sim["_sim_member"].get(i),
        })

    cat_counts = {}
    for p in promos:
        for h in (p["indicators"] if p else []):
            cat_counts[h["category"]] = cat_counts.get(h["category"], 0) + 1
    flagged = [c for c in comments if c["promo_signal"]]
    labels = {k: promo.CATEGORY_LABELS.get(k, k) for k in cat_counts}

    for k in ("_dup_member", "_sim_member", "_in_repeat"):
        sim.pop(k)

    return {
        "analysis_status": "analyzed",
        "data_source": {"type": "csv_upload", "filename": filename,
                        "analyzed_at": datetime.now(timezone.utc).isoformat()},
        "summary": {
            "total_comments": n,
            "sentiment": {k: {"count": v, "percent": _pct(v, n)} for k, v in counts.items()},
            "promotional_signals": len(flagged),
            "promotional_signals_percent": _pct(len(flagged), n),
            "comments_in_repeated_groups": sim["counts"]["comments_in_any_repeat"],
            "repeated_percent": _pct(sim["counts"]["comments_in_any_repeat"], n),
            "notable_coordination_indicators": coord["summary"]["notable_indicators"],
            "available_coordination_indicators": coord["summary"]["available_indicators"],
        },
        "sentiment": {"method": sentiment.METHOD, "evaluation": evaluation,
                      "evaluation_note": None if evaluation else
                      "No 'label' column with positive/neutral/negative values was found, so accuracy is unknown."},
        "promotional": {
            "disclaimer": "A promotional signal means the wording resembles promotion. It is not confirmed advertising.",
            "category_counts": [{"category": k, "label": labels[k], "count": v}
                                for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])],
            "keyword_categories": {k: promo.CATEGORY_LABELS.get(k, k) for k in promo_patterns},
        },
        "similarity": sim,
        "coordination": coord,
        "comments": comments,
        "quality": quality,
        "limitations": LIMITATIONS,
    }
