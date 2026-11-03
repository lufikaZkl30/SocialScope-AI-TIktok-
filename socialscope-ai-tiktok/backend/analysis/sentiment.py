"""Lexicon-based Indonesian sentiment BASELINE.

This is a transparent, rule-based baseline - NOT a trained model. It scores words from a small
hand-written Indonesian/English lexicon, handles simple negation ("tidak bagus") and intensifiers
("bagus banget"), and returns the matched terms so every label can be explained.
Known limits: no sarcasm, no context, small vocabulary, regional slang gaps. Its accuracy is
unknown until measured on labelled data (see `evaluate`).
"""
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

METHOD = {
    "id": "lexicon-baseline-id-v1",
    "name": "Indonesian lexicon baseline",
    "type": "rule-based (not a trained model)",
    "language": "Indonesian, with common English words and slang",
    "claims_accuracy": False,
}

POSITIVE = {w: 1.0 for w in """
bagus keren mantap suka cinta hebat top terbaik lucu kece indah cantik ganteng sukses semangat bangga
senang bahagia puas asik asyik seru baik bermanfaat inspiratif jos gokil amazing good love nice great
best wow salut respect menarik setuju hormat apresiasi dukung mendukung cakep manis sehat sabar adem
menghibur terharu amin aamiin berkah lancar untung worth rekomendasi sempurna cocok kreatif positif
membantu bermanfaat ramah rapi bersih nyaman enak lezat mantul juara berhasil hibur kagum
""".split()}
POSITIVE.update({"luar biasa": 2.0, "terima kasih": 1.0, "bagus banget": 2.0})
NEGATIVE = {w: -1.0 for w in """
jelek buruk benci bodoh goblok tolol bego sampah parah jahat bohong hoaks tipu penipu scam menyebalkan
kesal kecewa marah sedih rugi mahal lambat lemot rusak gagal malas bosan norak alay lebay cringe najis
anjing bangsat sialan brengsek kampret jijik muak bahaya korupsi koruptor curang zalim munafik fitnah
hina menghina mengecewakan annoying bad hate worst sucks trash toxic nyesel menyesal sombong kasar
berisik aneh ngawur salah palsu menjijikkan memalukan malu ancur hancur payah lelet
""".split()}
NEGATIVE.update({"gak jelas": -1.0})
STRONG = {"najis", "anjing", "bangsat", "brengsek", "goblok", "tolol", "penipu", "jijik", "muak"}
for w in STRONG:
    NEGATIVE[w] = -2.0
for w in ("hebat", "terbaik", "sempurna", "juara", "cinta"):
    POSITIVE[w] = 2.0

EMOJI = {"❤": 1, "😍": 1, "🥰": 1, "😘": 1, "👍": 1, "🔥": 1, "👏": 1, "😊": 1, "💯": 1, "✨": 0.5,
         "😁": 1, "😄": 1, "🤩": 1, "💕": 1, "💖": 1, "💗": 1, "👌": 1, "😂": 0.5, "🤣": 0.5,
         "😡": -1, "🤬": -2, "😠": -1, "👎": -1, "😢": -1, "😭": -0.5, "😤": -1, "🤮": -2,
         "💩": -1, "😞": -1, "😒": -1, "🙄": -1}
NEGATORS = {"gak", "tidak", "bukan", "belum", "jangan", "kurang", "tanpa", "nggak", "no", "not"}
INTENSIFIERS = {"banget", "sekali", "sangat", "amat", "super", "paling", "bener-bener"}
THRESHOLD = 1.0


def score_text(norm: str):
    tokens = norm.split()
    total, terms, i, neg_left = 0.0, [], 0, 0
    while i < len(tokens):
        tok, weight, span, name = tokens[i], None, 1, None
        if tok in NEGATORS:
            neg_left = 2  # negation reaches the next two tokens, and only the nearest sentiment word
        if i + 1 < len(tokens):
            bigram = f"{tok} {tokens[i + 1]}"
            lex2 = POSITIVE.get(bigram, NEGATIVE.get(bigram))
            if lex2 is not None:
                weight, span, name = lex2, 2, bigram
        if weight is None:
            weight = POSITIVE.get(tok, NEGATIVE.get(tok, EMOJI.get(tok)))
            name = tok
        if weight is not None:
            negated = neg_left > 0
            boosted = (i + span < len(tokens) and tokens[i + span] in INTENSIFIERS) or \
                      (i > 0 and tokens[i - 1] in INTENSIFIERS)
            w = -weight if negated else weight
            if boosted:
                w *= 1.5
            total += w
            terms.append(f"{'+' if w > 0 else '-'}{name}" + (" (negated)" if negated else ""))
            neg_left = 0
        elif tok not in NEGATORS:
            neg_left = max(0, neg_left - 1)
        i += span
    label = "positive" if total >= THRESHOLD else "negative" if total <= -THRESHOLD else "neutral"
    return label, round(total, 2), terms


def analyze_sentiment(norm_series):
    results = [score_text(t) for t in norm_series]
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for label, _, _ in results:
        counts[label] += 1
    return results, counts


LABEL_MAP = {"positive": "positive", "positif": "positive", "pos": "positive", "1": "positive",
             "negative": "negative", "negatif": "negative", "neg": "negative", "-1": "negative",
             "neutral": "neutral", "netral": "neutral", "neu": "neutral", "0": "neutral"}


def evaluate(true_labels, predicted):
    """Compare baseline predictions with the user's own labels. Returns None if no usable labels."""
    pairs = [(LABEL_MAP.get(str(t)), p) for t, p in zip(true_labels, predicted)]
    pairs = [(t, p) for t, p in pairs if t]
    if not pairs:
        return None
    y_true, y_pred = zip(*pairs)
    order = ["positive", "neutral", "negative"]
    prec, rec, f1, sup = precision_recall_fscore_support(y_true, y_pred, labels=order, zero_division=0)
    return {
        "n_labeled": len(pairs),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=order, average="macro", zero_division=0)), 4),
        "per_class": {c: {"precision": round(float(prec[i]), 3), "recall": round(float(rec[i]), 3),
                          "f1": round(float(f1[i]), 3), "support": int(sup[i])} for i, c in enumerate(order)},
        "confusion_matrix": {"labels": order,
                             "matrix": confusion_matrix(y_true, y_pred, labels=order).tolist()},
        "note": ("Computed only on the rows you labelled. "
                 + ("The labelled sample is small, so treat these numbers as unstable." if len(pairs) < 100 else
                    "Results describe this dataset only and may not generalise.")),
    }
