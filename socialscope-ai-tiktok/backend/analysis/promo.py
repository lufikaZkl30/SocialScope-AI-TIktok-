"""Promotional-language signals. A flag is a SIGNAL for review, never confirmed advertising."""
import json
import re

from .preprocessing import PHONE_RE, URL_RE

DEFAULT_KEYWORDS = {
    "contact_call_to_action": ["wa", "whatsapp", "dm", "chat aja", "hubungi", "klik link", "link di bio",
                               "link bio", "cek bio", "cek profil", "pesan sekarang", "order", "checkout",
                               "keranjang kuning", "kunjungi"],
    "offer_or_discount": ["diskon", "promo", "gratis", "cashback", "voucher", "flash sale", "harga spesial",
                          "free ongkir", "bonus", "potongan", "murah banget"],
    "selling_language": ["dijual", "open order", "preorder", "ready stok", "ready stock", "cod", "reseller",
                         "dropship", "agen", "grosir", "jual"],
    "follow_or_engagement_exchange": ["follow back", "f4f", "like back", "mampir ke", "follow akun",
                                      "support balik", "subscribe"],
    "giveaway_or_finance": ["giveaway", "undian", "hadiah", "pinjol", "slot", "gacor", "togel", "judi",
                            "investasi", "cuan", "passive income", "trading"],
}
CATEGORY_LABELS = {
    "contact_call_to_action": "Contact / call to action",
    "offer_or_discount": "Offer or discount",
    "selling_language": "Selling language",
    "follow_or_engagement_exchange": "Follow / engagement exchange",
    "giveaway_or_finance": "Giveaway or finance",
    "contains_link": "Contains a link",
    "contains_phone_number": "Contains a phone number",
}


def load_keywords(path=""):
    if path:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and all(isinstance(v, list) for v in data.values()):
            return {k: [str(x).lower() for x in v] for k, v in data.items()}
        raise ValueError("PROMO_KEYWORDS_PATH must contain a JSON object of keyword lists.")
    return DEFAULT_KEYWORDS


def compile_patterns(keywords):
    return {cat: [(kw, re.compile(r"(?<!\w)" + re.escape(kw) + r"(?!\w)")) for kw in kws]
            for cat, kws in keywords.items()}


def detect(raw_text: str, patterns):
    """Return a dict describing signals found in one comment, or None."""
    low = raw_text.lower()
    hits = []
    for cat, plist in patterns.items():
        found = [kw for kw, rx in plist if rx.search(low)]
        if found:
            hits.append({"category": cat, "matched": found[:5]})
    if URL_RE.search(raw_text):
        hits.append({"category": "contains_link", "matched": ["link"]})
    if PHONE_RE.search(raw_text):
        hits.append({"category": "contains_phone_number", "matched": ["phone number"]})
    if not hits:
        return None
    n = len({h["category"] for h in hits})
    return {
        "strength": "stronger" if n >= 2 else "weak",
        "indicators": hits,
        "reason": "; ".join(f"{CATEGORY_LABELS.get(h['category'], h['category'])}: {', '.join(h['matched'])}"
                            for h in hits),
    }
