"""Exploratory 'potential coordination indicators'.

These are statistical observations about the uploaded dataset. They are NOT proof of coordinated
behaviour, and this module never looks at or reports individual accounts.
"""
import numpy as np
import pandas as pd

DISCLAIMER = ("These are potential indicators only. Bursts, repeated text and cross-video repeats also "
              "occur naturally (viral trends, fan communities, memes, reposted challenges). No account "
              "or person is identified or accused by this analysis.")


def _iso(t):
    """Timestamps are stored as naive UTC; emit an explicit Z so browsers do not apply a local offset."""
    return pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strength(value, weak, moderate, strong):
    return "strong" if value >= strong else "moderate" if value >= moderate else "weak" if value >= weak else "none"


def _bucket_size(span_seconds):
    if span_seconds <= 2 * 3600:
        return "1min", "per minute"
    if span_seconds <= 2 * 86400:
        return "10min", "per 10 minutes"
    if span_seconds <= 45 * 86400:
        return "1h", "per hour"
    return "1D", "per day"


def time_analysis(df, in_repeat):
    ts = df["timestamp"].dropna()
    if len(ts) < 20:
        return None
    span = (ts.max() - ts.min()).total_seconds()
    if span <= 0:
        return None
    freq, label = _bucket_size(span)
    bucket = ts.dt.floor(freq)
    counts = bucket.value_counts().sort_index()
    full = counts.resample(freq).sum()  # fills empty buckets with 0; timestamps are naive UTC
    mean, sd = float(full.mean()), float(full.std(ddof=0))
    threshold = mean + 3 * sd
    bursts = []
    if sd > 0:
        for t, c in full[(full > threshold) & (full >= 5)].sort_values(ascending=False).head(5).items():
            rows = df.index[df["timestamp"].dt.floor(freq) == t]
            overlap = sum(1 for i in rows if i in in_repeat)
            bursts.append({"bucket_start": _iso(t), "comments": int(c),
                           "share_of_dated_comments": round(float(c) / len(ts), 4),
                           "share_also_repeated_text": round(overlap / max(len(rows), 1), 4)})
    chart, note = full, None
    if len(full) > 400:  # keep the chart light by summing neighbouring buckets
        step = int(np.ceil(len(full) / 400))
        chart = full.groupby(np.arange(len(full)) // step).sum()
        chart.index = full.index[::step][: len(chart)]
        note = f"Chart groups {step} consecutive buckets together; burst detection uses the full resolution."
    return {
        "bucket": label, "chart_note": note, "dated_comments": int(len(ts)),
        "first": _iso(ts.min()), "last": _iso(ts.max()),
        "series": [{"t": _iso(t), "count": int(c)} for t, c in chart.items()],
        "burst_threshold": round(threshold, 2) if sd > 0 else None, "bursts": bursts,
    }


def cross_video(df):
    vids = df["video_id"].dropna()
    if vids.nunique() < 2:
        return None
    sub = df[df["video_id"].notna() & (df["norm"].str.len() >= 12)]
    g = sub.groupby("norm")["video_id"].nunique()
    repeated = g[g >= 2].sort_values(ascending=False)
    rows = []
    for norm, n_vid in repeated.head(15).items():
        members = sub[sub["norm"] == norm]
        rows.append({"text": members.iloc[0]["display"][:140], "videos": int(n_vid), "comments": int(len(members))})
    n_comments = int(sub[sub["norm"].isin(repeated.index)].shape[0])
    return {"distinct_videos": int(vids.nunique()), "texts_repeated_across_videos": int(len(repeated)),
            "comments_involved": n_comments, "share_of_comments": round(n_comments / len(df), 4), "examples": rows}


def analyze_coordination(df, sim, quality):
    n = len(df)
    in_repeat = sim["_in_repeat"]
    t, cv = time_analysis(df, in_repeat), cross_video(df)
    share_rep = sim["counts"]["share_in_any_repeat"]
    indicators = [{
        "id": "repeated_text", "title": "Repeated or near-identical comments", "available": True,
        "value": share_rep, "value_label": f"{share_rep * 100:.1f}% of comments",
        "strength": _strength(share_rep, 0.05, 0.15, 0.30),
        "explanation": "Share of comments that belong to an exact-duplicate, normalized-duplicate or similar-text group.",
    }]
    if t:
        top = t["bursts"][0] if t["bursts"] else None
        v = top["share_of_dated_comments"] if top else 0
        indicators.append({
            "id": "time_concentration", "title": "Concentrated posting times", "available": True,
            "value": v, "value_label": (f"{v * 100:.1f}% of dated comments in the busiest burst window"
                                        if top else "No window stands out from the average"),
            "strength": _strength(v, 0.10, 0.25, 0.50) if top else "none",
            "explanation": f"Comment counts {t['bucket']} compared with the dataset's own average; "
                           "a window counts as a burst when it exceeds the mean by 3 standard deviations (min. 5 comments).",
        })
        overlap = top["share_also_repeated_text"] if top else 0
        indicators.append({
            "id": "burst_repetition", "title": "Repeated text inside bursts", "available": bool(top),
            "value": overlap, "value_label": (f"{overlap * 100:.1f}% of the top burst's comments also repeat text"
                                              if top else "No burst to examine"),
            "strength": _strength(overlap, 0.20, 0.40, 0.70) if top else "none",
            "explanation": "Whether the busiest time window also contains duplicated or similar wording.",
        })
    else:
        indicators.append({"id": "time_concentration", "title": "Concentrated posting times", "available": False,
                           "value": None, "value_label": "Unavailable", "strength": "unavailable",
                           "explanation": "Needs a timestamp column with at least 20 parseable values."})
    if cv:
        s = cv["share_of_comments"]
        indicators.append({"id": "cross_video", "title": "Same text across several videos", "available": True,
                           "value": s, "value_label": f"{s * 100:.1f}% of comments ({cv['texts_repeated_across_videos']} texts)",
                           "strength": _strength(s, 0.03, 0.10, 0.25),
                           "explanation": "Normalized comment texts that appear under two or more video IDs."})
    else:
        indicators.append({"id": "cross_video", "title": "Same text across several videos", "available": False,
                           "value": None, "value_label": "Unavailable", "strength": "unavailable",
                           "explanation": "Needs a video_id column with at least two different videos."})
    avail = [i for i in indicators if i["available"]]
    notable = [i for i in avail if i["strength"] in ("moderate", "strong")]
    return {
        "disclaimer": DISCLAIMER, "indicators": indicators,
        "summary": {"available_indicators": len(avail), "notable_indicators": len(notable),
                    "headline": (f"{len(notable)} of {len(avail)} available indicators show a moderate or strong signal."
                                 if avail else "No indicators could be computed."),
                    "sample_size_warning": n < 50},
        "time": t, "cross_video": cv,
    }
