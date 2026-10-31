#!/usr/bin/env python3
"""Sync the shop's product list from our eBay store.

Reads every active listing from seller EBAY_SELLER through eBay's Browse API
(app token, read-only public data) and rewrites assets/shop-products.csv,
which /shop/ and /shop/item/ read in the browser. Checkout stays on eBay.

Keys come from the env (EBAY_CLIENT_ID / EBAY_CLIENT_SECRET, set as GitHub
Actions secrets) or, locally, from ~/.config/nmutv/ebay_client_id and
~/.config/nmutv/ebay_client_secret.

Usage: python3 build/ebay_sync.py [--dry-run] [--force]
  --dry-run  print what would change, don't write
  --force    write even if the product count dropped by more than half
"""
import base64
import csv
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("SYNC_OUT") or os.path.join(ROOT, "assets", "shop-products.csv")
EBAY_SELLER = "gps-wheels"
API = "https://api.ebay.com"
MARKETPLACE = "EBAY_US"
SEARCH_CATEGORY = "6000"  # eBay Motors; all our listings live under it
# Listings never shown on the site, by eBay item number.
EXCLUDE_ITEM_IDS = {
    "900050715799",  # Range RA010 DFM Pro: emissions-defeat device, should be ended on eBay
}
COLUMNS = ["show", "category", "name", "price", "photo", "photos", "description", "details", "buy_link", "sku"]

# python.org Python on macOS has no CA bundle; GitHub's runner does.
SSL = ssl.create_default_context(cafile="/etc/ssl/cert.pem") if os.path.exists("/etc/ssl/cert.pem") else ssl.create_default_context()

# Sections of our listing template that are store boilerplate, not product info.
BOILERPLATE_HEADINGS = {"shipping", "returns", "payment", "about us", "delivery", "location", "we accept only",
                        "photos", "categories", "usefull link", "useful link", "why choose us ?", "why choose us"}
BOILERPLATE_LINES = re.compile(r"^(visit our store|read our feedback|view store|view feedback|©|&copy;|atv$|"
                               r"nmutv$|gps-wheels$|online powder coat$|quality truck, diesel and performance parts$|"
                               r"custom colors on parts you can.t find anywhere else$|"
                               r"(✓\s*)?(brand new|free us shipping|usa based|secure ebay checkout|powder coated in-house)\b)", re.I)


def secret(name):
    v = os.environ.get(name.upper())
    if v:
        return v.strip()
    path = os.path.expanduser(f"~/.config/nmutv/{name.lower()}")
    return open(path).read().strip() if os.path.exists(path) else ""


def http(method, url, headers=None, data=None, tries=4):
    for attempt in range(tries):
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=60, context=SSL) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(2 ** attempt * 3)
                continue
            raise SystemExit(f"eBay API error {e.code} on {url.split('?')[0]}: {body}")


def token():
    cid, csec = secret("ebay_client_id"), secret("ebay_client_secret")
    if not cid or not csec:
        raise SystemExit("Missing eBay keys (EBAY_CLIENT_ID / EBAY_CLIENT_SECRET).")
    auth = base64.b64encode(f"{cid}:{csec}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}).encode()
    r = http("POST", f"{API}/identity/v1/oauth2/token",
             {"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded"}, body)
    return r["access_token"]


def search_ids(tok):
    """All active item ids for our seller."""
    headers = {"Authorization": "Bearer " + tok, "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE}
    ids, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"category_ids": SEARCH_CATEGORY, "filter": f"sellers:{{{EBAY_SELLER}}}",
                                    "limit": 200, "offset": offset})
        r = http("GET", f"{API}/buy/browse/v1/item_summary/search?{q}", headers)
        page = r.get("itemSummaries", [])
        ids += [s["itemId"] for s in page]
        offset += len(page)
        if not page or offset >= r.get("total", 0) or offset >= 10000:
            return ids


def get_items(tok, ids):
    """Full item details, one call per listing. (The batch getItems call needs extra
    eBay approval; one-by-one fits the default 5,000 calls/day for a few hundred items.)"""
    headers = {"Authorization": "Bearer " + tok, "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE}
    items = []
    for item_id in ids:
        items.append(http("GET", f"{API}/buy/browse/v1/item/{urllib.parse.quote(item_id)}", headers))
        time.sleep(0.2)
    return items


class DescText(HTMLParser):
    """Listing description HTML -> plain text blocks. Table rows become "Label: value",
    list items become "- item", block elements become line breaks."""
    BLOCK = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "li", "ul", "ol", "table", "section"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.cells, self.skip = [], None, 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.skip += 1
        elif tag == "tr":
            self.cells = []
        elif tag in ("td", "th") and self.cells is not None:
            self.cells.append("")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.skip -= 1
        elif tag == "tr" and self.cells is not None:
            cells = [re.sub(r"\s+", " ", c).strip() for c in self.cells if c.strip()]
            if len(cells) >= 2:
                self.out.append("\n" + cells[0].rstrip(":") + ": " + " ".join(cells[1:]))
            elif cells:
                self.out.append("\n" + cells[0])
            self.cells = None
        elif tag in self.BLOCK and tag not in ("li", "td", "th"):
            self.out.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        if self.cells is not None and self.cells:
            self.cells[-1] += data
        elif self.cells is None:
            self.out.append(data)


def old_template_text(text):
    """Our pre-2026 listing template renders as one run of text. Keep the part between
    DESCRIPTION and Returns, and break it at the labels it uses."""
    m = re.search(r"DESCRIPTION\s*(.+?)\s*Returns\b", text, re.S)
    body = m.group(1) if m else ""
    body = re.sub(r"\s+", " ", body)
    body = re.sub(r"\s*(Fits |Direct replacement|Color:|Front:|Rear:)", r"\n\1", body)
    lines = [l.strip() for l in body.split("\n") if l.strip()]
    specs = [l for l in lines if re.match(r"^(Color|Front|Rear):", l)]
    prose = [l for l in lines if l not in specs]
    return "\n\n".join(prose + (["\n".join(specs)] if specs else []))


def description_blocks(html, title):
    if "eBay Listing Template" in (html or "")[:3000]:
        p = DescText()
        p.feed(html)
        return old_template_text(re.sub(r"[ \t\u00a0]+", " ", "".join(p.out)))
    p = DescText()
    p.feed(html or "")
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in "".join(p.out).split("\n")]
    keep, dropping = [], False
    for ln in lines:
        if not ln or ln == "-":
            keep.append("")
            continue
        low = ln.lower().rstrip(":")
        if low in BOILERPLATE_HEADINGS:
            dropping = True
            continue
        if low in ("highlights", "specifications", "fits", "description", "product details"):
            dropping = False
            keep.append("")
            if low == "fits":
                keep.append("Fits:")
            continue
        if dropping or BOILERPLATE_LINES.match(ln) or low == title.lower() or low.startswith("<!--"):
            continue
        keep.append(re.sub(r"^- ✓\s*", "- ", ln))
    text = "\n".join(keep)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\n\n(?=- )", "\n", text)          # list items stay together, under their heading
    # spec rows ("Label: value") separated only by blank lines -> one block, so the site shows a table
    spec = re.compile(r"^[^:\n]{1,40}: \S")
    lines = text.split("\n")
    merged = []
    for i, ln in enumerate(lines):
        if ln == "" and merged and spec.match(merged[-1]) and i + 1 < len(lines) and spec.match(lines[i + 1]):
            continue
        merged.append(ln)
    text = "\n".join(merged).strip()
    return text


# Shop categories by product type (first match wins); eBay's own leaf category is the fallback.
CATEGORY_RULES = [
    ("ATV Beadlock Wheels", r"\bbeadlocks?\b"),
    ("ATV Wheels", r"\b(wheels?|rims?)\b"),
    ("Steering Stabilizers", r"steering (stabilizer|damper)"),
    ("Shocks & Struts", r"\b(shocks?|struts?)\b"),
    ("Intake & Intercooler", r"intercooler|cold air intake|air filter|\bintake\b"),
    ("Exhaust", r"exhaust|muffler|down ?pipe|up-?pipe|tail ?pipe|\bheaders?\b|cat-?back"),
    ("Transmission", r"transmission"),
    ("Engine & Cooling", r"gasket|oil filter|turbo|coolant|valve|\bengine\b|radiator|thermostat"),
]


def category_for(item, title):
    for name, pattern in CATEGORY_RULES:
        if re.search(pattern, title, re.I):
            return name
    path = [c.strip() for c in (item.get("categoryPath") or "").split("|") if c.strip()]
    return path[-1] if path else "Other"


def to_row(item):
    title = item.get("title", "").strip()
    images = [item.get("image", {}).get("imageUrl", "")] + [i.get("imageUrl", "") for i in item.get("additionalImages", [])]
    images = [re.sub(r"/s-l\d+\.(jpg|jpeg|png|webp)$", "/s-l1600.jpg", u) for u in images if u]
    images = list(dict.fromkeys(images))
    aspects = {a["name"]: a["value"] for a in item.get("localizedAspects", []) if a.get("value")}
    body = description_blocks(item.get("description", ""), title)
    fits = re.search(r"^Fits:\n((?:- .+\n?)+)", body, re.M)
    short = ""
    if fits:
        short = "Fits: " + "; ".join(l[2:].strip() for l in fits.group(1).strip().split("\n"))
    else:
        f = re.search(r"^Fits:?\s+(.+)$", body, re.M | re.I)
        short = ("Fits: " + f.group(1).strip()) if f else ""
    spec_lines = [f"{k}: {v}" for k, v in aspects.items()
                  if k in ("Brand", "Manufacturer Part Number", "Placement on Vehicle", "Type", "Color", "Material",
                           "Rim Diameter", "Rim Width", "Bolt Pattern", "Offset", "Number of Wheels", "Fitment Type")
                  and f"{k}:".lower() not in body.lower()
                  and not (k == "Manufacturer Part Number" and "part number:" in body.lower())]
    if spec_lines:
        body = (body + "\n\n" + "\n".join(spec_lines)).strip()
    avail = (item.get("estimatedAvailabilities") or [{}])[0]
    in_stock = avail.get("estimatedAvailabilityStatus", "IN_STOCK") != "OUT_OF_STOCK"
    return {
        "show": "yes" if in_stock else "no",
        "category": category_for(item, title),
        "name": title,
        "price": item.get("price", {}).get("value", ""),
        "photo": images[0] if images else "",
        "photos": " | ".join(images[1:12]),
        "description": short[:300],
        "details": body,
        "buy_link": f"https://www.ebay.com/itm/{item.get('legacyItemId', '')}",
        "sku": item.get("legacyItemId", ""),
    }


def main():
    dry, force = "--dry-run" in sys.argv, "--force" in sys.argv
    tok = token()
    ids = search_ids(tok)
    rows = [to_row(it) for it in get_items(tok, ids)]
    rows = [r for r in rows if r["name"] and r["sku"] and r["sku"] not in EXCLUDE_ITEM_IDS]
    rows.sort(key=lambda r: (r["category"], r["name"]))
    previous = list(csv.DictReader(open(OUT, encoding="utf-8"))) if os.path.exists(OUT) else []
    print(f"eBay: {len(ids)} active listings -> {len(rows)} products (was {len(previous)})")
    if not rows:
        raise SystemExit("No listings came back from eBay; leaving the shop unchanged.")
    if previous and len(rows) < len(previous) / 2 and not force:
        raise SystemExit("Product count dropped by more than half; leaving the shop unchanged (use --force to override).")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    new = buf.getvalue()
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    if new == old:
        print("No changes.")
        return
    if dry:
        print(new[:3000])
        return
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
