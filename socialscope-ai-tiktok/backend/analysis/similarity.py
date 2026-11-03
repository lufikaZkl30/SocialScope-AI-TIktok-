"""Exact-duplicate, near-duplicate and repeated-phrase detection (TF-IDF + cosine similarity).

Repeated wording has many innocent causes (trends, copied catchphrases, memes, spam, coordination).
Nothing here labels a person or account.
"""
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

MIN_CHARS_FOR_SIMILARITY = 12
STOPWORDS = set("""yang dan di ke dari ini itu untuk dengan saya kamu dia kita mereka juga sudah belum
gak tidak bukan ada apa ya aja sih deh dong lah kok kan nya pada atau karena kalau bisa jadi lagi""".split())
NOTE = ("Repeated or similar wording can come from ordinary trends, copied catchphrases, spam or "
        "coordinated activity. It is not evidence about any person or account.")


def _preview(text, n=140):
    return text if len(text) <= n else text[: n - 1] + "…"


def exact_duplicates(df):
    """Groups of comments identical after trimming whitespace and ignoring letter case."""
    key = df["display"].str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    groups = []
    for _, idx in key.groupby(key).groups.items():
        if len(idx) >= 2:
            groups.append(list(idx))
    return groups


def normalized_duplicates(df, exact_groups):
    """Comments that become identical only after normalization (punctuation, stretched letters, slang)."""
    in_exact = {i for g in exact_groups for i in g}
    groups = []
    for _, idx in df["norm"].groupby(df["norm"]).groups.items():
        members = list(idx)
        displays = {df.at[i, "display"].lower().strip() for i in members}
        if len(members) >= 2 and len(displays) >= 2 and df.at[members[0], "norm"].strip():
            groups.append(members)
    return groups


def similar_groups(df, threshold, chunk=500):
    """Connected groups of distinct normalized texts whose TF-IDF cosine similarity >= threshold."""
    eligible = df[df["norm"].str.len() >= MIN_CHARS_FOR_SIMILARITY]
    grouped = eligible.groupby("norm").groups
    texts, members = list(grouped.keys()), [list(v) for v in grouped.values()]
    if len(texts) < 2:
        return [], {"unique_texts_compared": len(texts)}
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit_transform(texts)
    parent = list(range(len(texts)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    edges = []
    for start in range(0, len(texts), chunk):
        sims = (X[start:start + chunk] @ X.T).toarray()
        rows, cols = np.where(sims >= threshold)
        for r, c in zip(rows, cols):
            i = start + r
            if c > i:
                edges.append((i, c, float(sims[r, c])))
                parent[find(i)] = find(c)
    comp = defaultdict(list)
    for i in range(len(texts)):
        comp[find(i)].append(i)
    edge_by_root = defaultdict(list)
    for i, j, s in edges:
        edge_by_root[find(i)].append(s)
    groups = []
    for root, ids in comp.items():
        if len(ids) < 2:
            continue
        sims = edge_by_root[root]
        groups.append({"rows": [m for i in ids for m in members[i]],
                       "texts": [texts[i] for i in ids],
                       "avg_similarity": round(float(np.mean(sims)), 3),
                       "min_similarity": round(float(np.min(sims)), 3)})
    return groups, {"unique_texts_compared": len(texts)}


def repeated_phrases(df, min_count=3, top=20):
    """Word 3-grams and 4-grams appearing in at least `min_count` different comments."""
    if len(df) < min_count:
        return []
    try:
        cv = CountVectorizer(ngram_range=(3, 4), binary=True, min_df=min_count)
        M = cv.fit_transform(df["norm"])
    except ValueError:
        return []
    counts = np.asarray(M.sum(axis=0)).ravel()
    out = []
    for term, c in zip(cv.get_feature_names_out(), counts):
        words = term.split()
        if sum(w in STOPWORDS for w in words) > len(words) / 2:
            continue
        out.append({"phrase": term, "comments": int(c), "share": round(float(c) / len(df), 4)})
    out.sort(key=lambda x: (-x["comments"], -len(x["phrase"])))
    kept = []
    for item in out:  # drop sub-phrases that add nothing over a longer phrase with same count
        if not any(item["phrase"] in k["phrase"] and item["comments"] == k["comments"] for k in kept):
            kept.append(item)
    return kept[:top]


def analyze_similarity(df, threshold):
    exact = exact_duplicates(df)
    norm_dups = normalized_duplicates(df, exact)
    sim, meta = similar_groups(df, threshold)

    def pack(group_rows, kind):
        d = df.loc[group_rows]
        return {"kind": kind, "size": len(group_rows), "text": _preview(d.iloc[0]["display"]),
                "rows": [int(r) for r in d["row"].tolist()[:25]]}

    exact_out = sorted([pack(g, "exact") for g in exact], key=lambda x: -x["size"])
    norm_out = sorted([pack(g, "normalized") for g in norm_dups], key=lambda x: -x["size"])
    sim_out = []
    for g in sorted(sim, key=lambda g: -len(g["rows"])):
        d = df.loc[g["rows"]]
        sim_out.append({"size": len(g["rows"]), "distinct_texts": len(g["texts"]),
                        "avg_similarity": g["avg_similarity"], "min_similarity": g["min_similarity"],
                        "examples": [_preview(t) for t in d["display"].drop_duplicates().tolist()[:5]],
                        "rows": [int(r) for r in d["row"].tolist()[:25]]})

    # Per-comment memberships (positional index in df)
    dup_member = {}
    for gid, g in enumerate(exact + norm_dups, 1):
        for i in g:
            dup_member.setdefault(i, gid)
    sim_member = {}
    for gid, g in enumerate(sim, 1):
        for i in g["rows"]:
            sim_member[i] = gid
    in_repeat = set(dup_member) | set(sim_member)

    n = len(df)
    return {
        "threshold": threshold,
        "note": NOTE,
        "exact_duplicate_groups": exact_out[:50],
        "normalized_duplicate_groups": norm_out[:50],
        "similar_groups": sim_out[:50],
        "repeated_phrases": repeated_phrases(df),
        "counts": {
            "exact_duplicate_groups": len(exact), "comments_in_exact_duplicates": len({i for g in exact for i in g}),
            "normalized_duplicate_groups": len(norm_dups),
            "similar_groups": len(sim), "comments_in_similar_groups": len(sim_member),
            "comments_in_any_repeat": len(in_repeat),
            "share_in_any_repeat": round(len(in_repeat) / n, 4) if n else 0,
            **meta,
        },
        "_dup_member": dup_member, "_sim_member": sim_member, "_in_repeat": in_repeat,
    }
