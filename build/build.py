#!/usr/bin/env python3
"""Static site generator for nmutv.com.

Run from anywhere:  python3 build/build.py
Writes HTML into the repo root (served by GitHub Pages).
"""
import json
import math
import os
import re
import unicodedata
from datetime import date
from html import escape

from data import CITIES, MODELS, REGIONS, SERVICES, SHOP, SITE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = date.today().isoformat()
DOMAIN = SITE["domain"]
PHONE = SITE["phone"]
TEL = SITE["phone_e164"]
EMAIL = SITE["email"]
ADDR_LINE = f'{SITE["street"]}, {SITE["city"]}, {SITE["state"]} {SITE["zip"]}'
MAP_EMBED = "https://www.google.com/maps?q=1261+Frontage+Rd+NW,+Socorro,+NM+87801&output=embed"
MAP_LINK = "https://www.google.com/maps/search/?api=1&query=1261+Frontage+Rd+NW+Socorro+NM+87801"

SITEMAP = []


# ---------------------------------------------------------------- helpers

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def pick(options, key, salt=0):
    """Deterministic per-city choice so each page reads differently."""
    h = sum((i + 1) * ord(c) for i, c in enumerate(key)) + salt * 7919
    return options[h % len(options)]


def miles_from_shop(lat, lon):
    r = 3958.8
    p1, p2 = math.radians(SHOP[0]), math.radians(lat)
    dp, dl = p2 - p1, math.radians(lon - SHOP[1])
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    straight = 2 * r * math.asin(math.sqrt(a))
    road = straight * 1.2  # rough road-mile estimate
    return int(round(road / 5.0) * 5)


def write(path, html, priority="0.6"):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(html)
    if path.endswith("index.html"):
        url = DOMAIN + "/" + path[: -len("index.html")]
        SITEMAP.append((url, priority))


def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>"


BUSINESS_ID = DOMAIN + "/#business"


def business_schema():
    return {
        "@context": "https://schema.org",
        "@type": "AutoRepair",
        "@id": BUSINESS_ID,
        "name": SITE["name"],
        "alternateName": SITE["legal_name"],
        "description": "UTV and side-by-side repair shop in Socorro, New Mexico. Engine work, engine swaps, suspension, belts and clutches, tires and wheels, crash repair, radio and accessory installs, with pickup and delivery across New Mexico.",
        "url": DOMAIN + "/",
        "telephone": TEL,
        "email": EMAIL,
        "image": DOMAIN + "/assets/og-image.png",
        "logo": DOMAIN + "/assets/logo-large.png",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": SITE["street"],
            "addressLocality": SITE["city"],
            "addressRegion": SITE["state"],
            "postalCode": SITE["zip"],
            "addressCountry": "US",
        },
        "geo": {"@type": "GeoCoordinates", "latitude": SITE["lat"], "longitude": SITE["lon"]},
        "areaServed": {"@type": "State", "name": "New Mexico"},
        "founder": {"@type": "Person", "name": SITE["owner"]},
        "priceRange": "$$",
        "hasMap": MAP_LINK,
    }


def breadcrumb_schema(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": DOMAIN + url}
            for i, (name, url) in enumerate(items)
        ],
    }


def faq_schema(faqs):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub("<[^>]+>", "", a)}}
            for q, a in faqs
        ],
    }


def faq_html(faqs, heading):
    items = "".join(
        f'<details class="faq"><summary>{escape(q)}</summary><p>{a}</p></details>' for q, a in faqs
    )
    return f'<section class="section"><div class="wrap narrow"><h2>{heading}</h2>{items}</div></section>'


def crumbs_html(items):
    parts = []
    for i, (name, url) in enumerate(items):
        if i == len(items) - 1:
            parts.append(f'<span aria-current="page">{escape(name)}</span>')
        else:
            parts.append(f'<a href="{url}">{escape(name)}</a>')
    return '<nav class="crumbs wrap" aria-label="Breadcrumb">' + " / ".join(parts) + "</nav>"


# ---------------------------------------------------------------- layout

TOP_CITY_NAMES = ["Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe", "Los Lunas", "Belen",
                  "Socorro", "Truth or Consequences", "Roswell", "Farmington", "Alamogordo", "Hobbs"]


def city_url(name):
    return f"/utv-repair/{slugify(name)}-nm/"


def page(path, title, desc, body, schemas=(), priority="0.6", og_type="website"):
    url = DOMAIN + "/" + (path[: -len("index.html")] if path.endswith("index.html") else path)
    schema_tags = "".join(jsonld(s) for s in schemas)
    top_cities = "".join(f'<li><a href="{city_url(c)}">{c} UTV Repair</a></li>' for c in TOP_CITY_NAMES)
    footer_services = "".join(f'<li><a href="/services/{s["slug"]}/">{s["short"]}</a></li>' for s in SERVICES[:8])
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="geo.region" content="US-NM">
<meta name="geo.placename" content="Socorro">
<meta name="geo.position" content="{SITE['lat']};{SITE['lon']}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{SITE['name']}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{DOMAIN}/assets/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#000000">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/assets/favicon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css?v={TODAY.replace('-', '')}">
{schema_tags}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap header-row">
    <a class="brand" href="/" aria-label="NM UTV home">
      <img src="/assets/logo.png" width="281" height="128" alt="NM UTV - UTV &amp; side-by-side repair, Socorro NM">
    </a>
    <input type="checkbox" id="nav-toggle" class="nav-toggle" aria-label="Open menu">
    <label for="nav-toggle" class="nav-btn" aria-hidden="true"><span></span><span></span><span></span></label>
    <nav class="main-nav" aria-label="Main">
      <a href="/services/">Services</a>
      <a href="/models/">Models</a>
      <a href="/utv-repair/">Service Areas</a>
      <a href="/about/">About</a>
      <a href="/contact/">Contact</a>
      <a class="btn btn-sm" href="tel:{TEL}">Call {PHONE}</a>
    </nav>
  </div>
</header>
<main id="main">
{body}
</main>
<section class="cta-band">
  <div class="wrap cta-row">
    <div>
      <h2>Need your UTV fixed?</h2>
      <p>Call NM UTV in Socorro. Pickup and delivery available anywhere in New Mexico.</p>
    </div>
    <div class="cta-actions">
      <a class="btn" href="tel:{TEL}">Call {PHONE}</a>
      <a class="btn btn-ghost" href="mailto:{EMAIL}">Email {EMAIL}</a>
    </div>
  </div>
</section>
<footer class="site-footer">
  <div class="wrap footer-grid">
    <div>
      <p class="footer-brand"><img src="/assets/logo.png" width="176" height="80" alt="NM UTV" loading="lazy"></p>
      <p>UTV &amp; side-by-side repair<br>{SITE['street']}<br>{SITE['city']}, {SITE['state']} {SITE['zip']}</p>
      <p><a href="tel:{TEL}">{PHONE}</a><br><a href="mailto:{EMAIL}">{EMAIL}</a></p>
      <p><a href="{MAP_LINK}" rel="noopener" target="_blank">Get directions</a></p>
    </div>
    <div>
      <p class="footer-h">Services</p>
      <ul>{footer_services}<li><a href="/services/">All services</a></li></ul>
    </div>
    <div>
      <p class="footer-h">Popular service areas</p>
      <ul>{top_cities}<li><a href="/utv-repair/">All New Mexico cities</a></li></ul>
    </div>
  </div>
  <div class="wrap footer-bottom">
    <p>&copy; {date.today().year} NM UTV, Socorro, New Mexico. Not affiliated with Polaris, BRP/Can-Am, Honda, Kawasaki, Yamaha, CFMOTO or Textron. Brand names are used only to describe the vehicles we service.</p>
  </div>
</footer>
<a class="call-fab" href="tel:{TEL}" aria-label="Call NM UTV">Call {PHONE}</a>
</body>
</html>
"""
    write(path, html, priority)


def hero(h1, lead, eyebrow="Socorro, NM · Serving all of New Mexico"):
    return f"""<section class="hero">
  <div class="wrap">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{h1}</h1>
    <p class="lead">{lead}</p>
    <div class="hero-actions">
      <a class="btn" href="tel:{TEL}">Call {PHONE}</a>
      <a class="btn btn-ghost" href="/services/utv-pickup-delivery/">Pickup &amp; delivery</a>
    </div>
    <ul class="hero-points">
      <li>Certified, experienced mechanics</li>
      <li>Quick turnaround</li>
      <li>Fair, upfront pricing</li>
      <li>Statewide pickup &amp; delivery</li>
    </ul>
  </div>
</section>"""


def location_box(extra=""):
    return f"""<aside class="loc-box">
  <p class="loc-h">Our shop</p>
  <p><strong>NM UTV</strong><br>{SITE['street']}<br>{SITE['city']}, {SITE['state']} {SITE['zip']}</p>
  {extra}
  <p><a href="tel:{TEL}">{PHONE}</a><br><a href="mailto:{EMAIL}">{EMAIL}</a></p>
  <p class="small">Pickup and delivery of your UTV is available anywhere in New Mexico for a fee.</p>
  <a class="btn btn-block" href="tel:{TEL}">Call for a quote</a>
</aside>"""


def service_cards(city=None):
    cards = []
    for s in SERVICES:
        label = s["short"]
        cards.append(
            f'<a class="card" href="/services/{s["slug"]}/"><h3>{escape(label)}</h3>'
            f'<p>{escape(s["intro"].split(". ")[0])}.</p></a>'
        )
    return '<div class="cards">' + "".join(cards) + "</div>"


def model_chips(brand=None):
    out = []
    for m in MODELS:
        if brand and m["brand"] != brand:
            continue
        out.append(f'<li><a href="/models/{m["slug"]}/">{escape(m["name"])}</a></li>')
    return '<ul class="chips">' + "".join(out) + "</ul>"


OWNER_BLURB = (
    "NM UTV proudly serves the entire state of New Mexico, owned by a former member of the "
    "<strong>factory Can-Am ATV racing team</strong>, "
    '<a href="https://www.knfilters.eu/gr/blog/kn-s-can-am-motoworks-finishes-first-third-and-fifth-in-worcs-season-opener/" '
    'target="_blank" rel="noopener"><strong>Dillon Zimmerman</strong></a> '
    '(<a href="https://dirtwheelsmag.com/can-ams-dillon-zimmerman-3rd-at-worcs-opener-in-atv-pro-class/" '
    'target="_blank" rel="noopener">see his WORCS ATV Pro results</a>), '
    "with a long history in the powersports industry. "
    "That racing background shows up in how we work: we know how these machines are built, how they fail, "
    "and how to make them last. Our mechanics are certified and have been working on side-by-sides for years, "
    "our turnaround times are quick, and our prices are very competitive. "
    "Over the years, we&rsquo;ve seen how dealerships and other shops take advantage of customers, and "
    "we&rsquo;re here to change that. We&rsquo;re bringing New Mexico a UTV repair source that delivers a level "
    "of honesty, quality, and expertise the state has never experienced before."
)


# ---------------------------------------------------------------- city pages

INTRO = [
    "Looking for <strong>{city} UTV repair</strong> you can trust? NM UTV is a full-service side-by-side shop in Socorro, and we take care of riders from {city} and across {county} County every week. With pickup and delivery available, getting your machine fixed doesn't mean losing a weekend to the trailer.",
    "If you have been searching for a <strong>UTV shop in {city}</strong>, NM UTV is a dedicated side-by-side repair shop in Socorro that serves {city} riders with statewide pickup and delivery. From a blown belt to a full engine rebuild, we fix it right and get it back to you fast.",
    "NM UTV handles <strong>{city} side-by-side repair</strong> for sport riders, hunters, ranchers and work crews. Our shop is in Socorro, but we pick up and deliver UTVs from {city} and the rest of {county} County, so a trip to the shop is as easy as a phone call.",
    "From Polaris RZRs to Can-Am X3s, NM UTV is the <strong>{city} UTV repair</strong> option built around side-by-sides. We are a dedicated UTV shop in Socorro with certified mechanics, quick turnaround and pickup and delivery from {city}.",
]

POLARIS = [
    "Polaris is the brand we see most from {city}. Whether you need <strong>{city} Polaris RZR 1000 repair</strong>, a belt and clutch service on a RZR 900, or a full service on a Ranger XP 1000, our techs work on Polaris side-by-sides every day. We repair the RZR XP 1000, RZR Pro XP, Pro R, Turbo R, RZR 900, RZR S 900, Trail 900, RZR 570, Ranger and General.",
    "Need a <strong>Polaris shop for {city}</strong>? We service and repair every Polaris side-by-side, including the RZR XP 1000, RZR Pro XP, Turbo R, RZR 900 and Trail 900, Rangers and Generals. Common jobs for {city} Polaris owners include belts, clutches, radius rods, ball joints, wheel bearings and full engine rebuilds.",
    "{city} riders bring us Polaris machines of every age, from high-hour RZR 900s to brand-new Pro Rs. If you are looking for <strong>{city} Polaris 1000 repair</strong> or a <strong>Polaris 900 shop</strong> that knows these machines inside and out, we handle RZR, Ranger and General repairs from routine service to engine swaps.",
]

CANAM = [
    "Our owner raced on the factory Can-Am team, so Can-Am machines are close to home for us. For <strong>{city} Can-Am X3 repair</strong> we handle belts, clutches, turbo and boost problems, trailing arms, bearing carriers, engine rebuilds and crash damage, along with Maverick R, Maverick Sport, Maverick Trail, Commander and Defender models.",
    "Looking for a <strong>Can-Am shop near {city}</strong>? We repair the Maverick X3 and X3 Turbo RR, the Maverick R, Maverick Sport and Trail, the Commander and the Defender. From a {city} Can-Am X3 belt replacement to a full Rotax engine rebuild, we know these machines well.",
    "Can-Am owners from {city} get a shop with real factory Can-Am racing experience behind it. We do <strong>Can-Am Maverick X3 repair</strong>, Defender and Commander service, engine work, suspension, crash repair and accessory installs for {city} riders.",
]

OTHER_BRANDS = [
    "We also work on Honda Talon and Pioneer, Kawasaki Teryx KRX 1000, Teryx and Mule, Yamaha YXZ1000R, Wolverine and Viking, CFMOTO ZFORCE and UFORCE, and Arctic Cat and Textron Wildcat side-by-sides. If it is a UTV and it lives in or around {city}, we can fix it.",
    "Not riding a Polaris or Can-Am? No problem. {city} riders bring us Honda Talons and Pioneers, Kawasaki KRX and Mule models, Yamaha YXZ and Wolverine models, CFMOTO and Textron machines, and we service them all.",
]

PICKUP = [
    "Our shop is at 1261 Frontage Rd NW in Socorro, roughly {miles} miles from {city}. If you can't haul your machine in, we offer <strong>UTV pickup and delivery from {city}</strong> for a fee. We pick it up from your home, ranch, job site or trailhead, repair it at our Socorro shop, and bring it back when it is done. Call {phone} for a pickup quote.",
    "We are located at 1261 Frontage Rd NW, Socorro, NM 87801, about {miles} miles from {city}. You are always welcome to drop your side-by-side off, but most {city} customers take advantage of our <strong>pickup and delivery service</strong>. It is available across New Mexico for a fee based on distance. Call {phone} to schedule.",
    "NM UTV is based in Socorro at 1261 Frontage Rd NW, roughly {miles} miles from {city}. To make it easy, we provide <strong>statewide UTV pickup and delivery</strong> for a fee. Tell us where your machine is in {city} and we will handle the rest.",
]

WHY = [
    "Why {city} riders choose NM UTV",
    "Why {city} side-by-side owners trust our shop",
    "What makes us the right UTV shop for {city}",
]


def city_faqs(city, county, miles, home):
    where = (
        f"NM UTV is located at {ADDR_LINE}. We are right here in Socorro, so you can drop off your machine or we can pick it up for you."
        if home else
        f"NM UTV is located at {ADDR_LINE}, roughly {miles} miles from {city}. We serve {city} and {county} County with pickup and delivery for a fee, so you don't need a trailer to get your UTV to our shop."
    )
    return [
        (f"Where is NM UTV located, and how far is it from {city}?", where),
        (f"Do you offer UTV pickup and delivery in {city}?",
         f"Yes. We pick up side-by-sides in {city} and anywhere else in New Mexico, repair them at our Socorro shop, and deliver them back when the work is done. Pickup and delivery is available for a fee based on distance. Call {PHONE} for a quote."),
        (f"Can you repair my Polaris RZR 1000 or Can-Am X3 from {city}?",
         f"Absolutely. Polaris RZR XP 1000, RZR 900, Pro XP and Ranger models and Can-Am Maverick X3, Maverick R and Defender models are among the machines we work on most. We handle everything from belts and clutches to engine rebuilds and engine swaps."),
        (f"What UTV repairs do you do for {city} customers?",
         "Everything from installing new radios and stereos to engine work, engine swaps, suspension work, new tires and wheels, belt installations, clutch service, crash repairs, electrical diagnosis, lighting and accessory installs, and routine maintenance."),
        ("How long does a UTV repair take?",
         "Our turnaround time is quick. Most maintenance, belt and accessory jobs are done fast, and we will give you a clear timeline after diagnosing bigger jobs like engine rebuilds or crash repairs, which can depend on parts availability."),
        ("Who works on my side-by-side?",
         f"Our mechanics are certified and have been working on UTVs for a long time. The shop is owned by {SITE['owner']}, a former factory Can-Am ATV racing team member with a long history in the powersports industry."),
    ]


def nearest(city_name, lat, lon, n=6):
    out = []
    for c in CITIES:
        if c[0] == city_name:
            continue
        d = math.hypot(c[2] - lat, (c[3] - lon) * math.cos(math.radians(lat)))
        out.append((d, c[0]))
    out.sort()
    return [name for _, name in out[:n]]


def build_city(c):
    name, county, lat, lon, region_key, local = c
    region = REGIONS[region_key]
    home = region_key == "home" and name == "Socorro"
    miles = miles_from_shop(lat, lon)
    slug = slugify(name) + "-nm"
    path = f"utv-repair/{slug}/index.html"
    fmt = dict(city=name, county=county, miles=miles, phone=PHONE)

    title = f"{name} UTV Repair & Side-by-Side Shop | Polaris RZR & Can-Am X3 | NM UTV"
    if len(name) > 14:
        title = f"{name} UTV Repair & Side-by-Side Shop | NM UTV"
    if home:
        desc = f"Socorro, NM UTV repair shop at 1261 Frontage Rd NW. Polaris RZR 1000, RZR 900, Can-Am X3, Ranger & more. Certified mechanics, fast turnaround. Call {PHONE}."
    else:
        desc = f"{name}, NM UTV repair & side-by-side service: Polaris RZR 1000, RZR 900, Can-Am X3, Ranger & more. Pickup & delivery from {name} to our Socorro shop. Call {PHONE}."

    dist_line = (
        '<p class="small">Right here in Socorro. Drop off or ask about local pickup.</p>' if home
        else f'<p class="small">Roughly {miles} miles from {escape(name)}.</p>'
    )

    intro = pick(INTRO, name).format(**fmt)
    polaris = pick(POLARIS, name, 1).format(**fmt)
    canam = pick(CANAM, name, 2).format(**fmt)
    other = pick(OTHER_BRANDS, name, 3).format(**fmt)
    pickup = pick(PICKUP, name, 4).format(**fmt)
    if home:
        pickup = (f"Our shop is at 1261 Frontage Rd NW in Socorro, right off the frontage road. Drop your machine off, "
                  f"or call {PHONE} and we can pick it up. We also offer pickup and delivery anywhere in New Mexico for a fee.")
    why_h = pick(WHY, name, 5).format(**fmt)

    local_html = f"<p>{escape(local)}</p>" if local else ""
    terrain = (f"<p>Around {escape(name)} and {escape(region['label'])}, riding usually means {region['terrain']}. "
               f"{region['wear']}</p>")

    model_links = []
    for m in MODELS:
        model_links.append(f'<li><a href="/models/{m["slug"]}/">{escape(name)} {escape(m["short"])} repair</a></li>')

    near = nearest(name, lat, lon)
    near_links = "".join(f'<li><a href="{city_url(n)}">{escape(n)} UTV repair</a></li>' for n in near)

    faqs = city_faqs(name, county, miles, home)
    crumbs = [("Home", "/"), ("Service Areas", "/utv-repair/"), (f"{name} UTV Repair", f"/utv-repair/{slug}/")]

    services_list = "".join(
        f'<li><a href="/services/{s["slug"]}/">{escape(s["short"])}</a></li>' for s in SERVICES
    )

    body = f"""{crumbs_html(crumbs)}
{hero(f"{escape(name)} UTV Repair &amp; Side-by-Side Service",
      f"Polaris, Can-Am, Honda, Yamaha, Kawasaki and more. Certified mechanics at our Socorro, NM shop with pickup and delivery from {escape(name)}.",
      eyebrow=f"Serving {escape(name)}, NM · Shop in Socorro")}
<section class="section">
  <div class="wrap split">
    <div class="prose">
      <h2>{escape(name)} UTV shop &amp; side-by-side repair</h2>
      <p>{intro}</p>
      {local_html}
      {terrain}
      <h2>{escape(name)} Polaris repair: RZR 1000, RZR 900, Ranger &amp; more</h2>
      <p>{polaris}</p>
      <h2>{escape(name)} Can-Am repair: Maverick X3, Defender &amp; Commander</h2>
      <p>{canam}</p>
      <h2>Honda, Yamaha, Kawasaki &amp; CFMOTO service</h2>
      <p>{other}</p>
    </div>
    {location_box(dist_line)}
  </div>
</section>
<section class="section alt">
  <div class="wrap">
    <h2>UTV services for {escape(name)} riders</h2>
    <p class="sub">We do everything from installing new radios to engine work, engine swaps, suspension work, new tires and wheels, belt installations and crash repairs.</p>
    {service_cards()}
  </div>
</section>
<section class="section">
  <div class="wrap split">
    <div class="prose">
      <h2>UTV pickup &amp; delivery {"in Socorro" if home else "from " + escape(name)}</h2>
      <p>{pickup}</p>
      <h2>{escape(why_h)}</h2>
      <p>{OWNER_BLURB}</p>
      <ul class="checks">
        <li><strong>Certified mechanics</strong> with years of UTV experience</li>
        <li><strong>Quick turnaround</strong> so you are back riding or working sooner</li>
        <li><strong>Great prices</strong> and upfront quotes before we start</li>
        <li><strong>Pickup and delivery</strong> from {escape(name)} and anywhere in New Mexico</li>
      </ul>
    </div>
    <div class="side-list">
      <p class="loc-h">Side-by-sides we repair for {escape(name)}</p>
      <ul class="link-list">{''.join(model_links)}</ul>
    </div>
  </div>
</section>
{faq_html(faqs, f"{escape(name)} UTV repair FAQ")}
<section class="section alt">
  <div class="wrap">
    <h2>Nearby service areas</h2>
    <ul class="chips">{near_links}<li><a href="/utv-repair/">All New Mexico cities</a></li></ul>
  </div>
</section>"""

    service_schema = {
        "@context": "https://schema.org",
        "@type": "Service",
        "serviceType": "UTV and side-by-side repair",
        "name": f"{name} UTV Repair",
        "provider": {"@id": BUSINESS_ID},
        "areaServed": {
            "@type": "City",
            "name": name,
            "containedInPlace": {"@type": "State", "name": "New Mexico"},
        },
        "description": desc,
    }
    page(path, title, desc, body,
         schemas=[business_schema(), service_schema, breadcrumb_schema(crumbs), faq_schema(faqs)],
         priority="0.8")


# ---------------------------------------------------------------- hubs

def region_groups():
    groups = {}
    order = ["home", "middle_rio", "metro", "east_mountain", "southern", "southwest", "mountain",
             "plains", "oilfield", "northern", "northwest"]
    names = {
        "home": "Socorro County",
        "middle_rio": "Middle Rio Grande Valley",
        "metro": "Albuquerque Metro",
        "east_mountain": "East Mountains & Estancia Valley",
        "southern": "Southern New Mexico",
        "southwest": "Southwest New Mexico",
        "mountain": "Mountain Towns",
        "plains": "Eastern Plains",
        "oilfield": "Permian Basin",
        "northern": "Northern New Mexico",
        "northwest": "Northwest New Mexico",
    }
    for c in CITIES:
        groups.setdefault(c[4], []).append(c[0])
    return [(names[k], sorted(groups[k])) for k in order if k in groups]


def all_cities_html():
    blocks = []
    for label, names in region_groups():
        links = "".join(f'<li><a href="{city_url(n)}">{escape(n)} UTV repair</a></li>' for n in names)
        blocks.append(f'<div class="region"><h3>{escape(label)}</h3><ul class="link-list">{links}</ul></div>')
    return '<div class="regions">' + "".join(blocks) + "</div>"


def build_home():
    faqs = [
        ("Where is NM UTV located?",
         f"Our shop is at {ADDR_LINE}. We serve Socorro and the entire state of New Mexico with pickup and delivery for a fee."),
        ("What kinds of UTV repair do you do?",
         "Everything from installing new radios and stereos to engine work, engine swaps, suspension work, new tires and wheels, belt installations, clutch service, crash repairs, electrical diagnosis and routine maintenance."),
        ("What brands of side-by-side do you work on?",
         "Polaris (RZR XP 1000, RZR Pro XP, RZR 900, Ranger, General), Can-Am (Maverick X3, Maverick R, Commander, Defender), Honda (Talon, Pioneer), Kawasaki (Teryx KRX, Teryx, Mule), Yamaha (YXZ1000R, Wolverine, Viking), CFMOTO and Arctic Cat/Textron."),
        ("Do you pick up UTVs outside of Socorro?",
         f"Yes. We offer UTV pickup and delivery anywhere in New Mexico for a fee based on distance, including Albuquerque, Las Cruces, Los Lunas, Belen, Rio Rancho, Santa Fe, Truth or Consequences and more. Call {PHONE} for a quote."),
        ("Who owns NM UTV?",
         f"NM UTV is owned by {SITE['owner']}, a former member of the factory Can-Am ATV racing team with a long history in the powersports industry."),
    ]
    models = "".join(
        f'<a class="card card-model" href="/models/{m["slug"]}/"><span class="tag">{escape(m["brand"])}</span>'
        f'<h3>{escape(m["name"])}</h3></a>' for m in MODELS
    )
    body = f"""{hero("UTV &amp; Side-by-Side Repair in Socorro, New Mexico",
      "Polaris RZR, Can-Am X3, Ranger, Defender, Talon and more. Certified mechanics, quick turnaround, great prices, and pickup and delivery anywhere in New Mexico.")}
<section class="section">
  <div class="wrap split">
    <div class="prose">
      <h2>Socorro's dedicated UTV repair shop</h2>
      <p>NM UTV is a full-service <strong>UTV and side-by-side repair shop in Socorro, NM</strong>. We fix sport machines, hunting rigs, ranch side-by-sides and oil field work UTVs, and we serve riders across all of New Mexico with pickup and delivery.</p>
      <p>We do everything from <a href="/services/utv-stereo-radio-install/">installing new radios</a> to <a href="/services/utv-engine-repair/">engine work</a>, <a href="/services/utv-engine-swaps/">engine swaps</a>, <a href="/services/utv-suspension-repair/">suspension work</a>, <a href="/services/utv-tires-wheels/">new tires and wheels</a>, <a href="/services/utv-belt-clutch-service/">belt installations</a> and <a href="/services/utv-crash-repair/">crash repairs</a>. If it is a side-by-side, we can fix it.</p>
      <h2>Owned by a factory Can-Am racer</h2>
      <p>{OWNER_BLURB}</p>
    </div>
    {location_box('<p class="small">Just off the frontage road in Socorro.</p>')}
  </div>
</section>
<section class="section alt">
  <div class="wrap">
    <h2>UTV repair services</h2>
    <p class="sub">One shop for every part of your side-by-side.</p>
    {service_cards()}
  </div>
</section>
<section class="section">
  <div class="wrap">
    <h2>Side-by-sides we repair</h2>
    <p class="sub">Polaris RZR 1000 and RZR 900, Can-Am Maverick X3, Rangers, Defenders and every other major brand.</p>
    <div class="cards cards-models">{models}</div>
  </div>
</section>
<section class="section alt">
  <div class="wrap">
    <h2>UTV pickup &amp; delivery across New Mexico</h2>
    <p class="sub">We are located in Socorro and pick up and deliver side-by-sides statewide for a fee. Find your city:</p>
    {all_cities_html()}
  </div>
</section>
<section class="section">
  <div class="wrap">
    <h2>Visit the shop</h2>
    <p class="sub">{ADDR_LINE} · <a href="tel:{TEL}">{PHONE}</a></p>
    <div class="map"><iframe title="NM UTV location map" src="{MAP_EMBED}" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe></div>
  </div>
</section>
{faq_html(faqs, "UTV repair FAQ")}"""
    page("index.html", "NM UTV | UTV & Side-by-Side Repair Shop in Socorro, New Mexico",
         f"Socorro, NM UTV & side-by-side repair shop. Polaris RZR, Can-Am X3, Ranger, Defender & more. Engine work, suspension, belts, tires, crash repair. Statewide pickup & delivery. {PHONE}",
         body, schemas=[business_schema(), faq_schema(faqs),
                        {"@context": "https://schema.org", "@type": "WebSite", "name": SITE["name"], "url": DOMAIN + "/"}],
         priority="1.0")


def build_areas_hub():
    crumbs = [("Home", "/"), ("Service Areas", "/utv-repair/")]
    body = f"""{crumbs_html(crumbs)}
{hero("UTV Repair Service Areas in New Mexico",
      "Our shop is in Socorro, and we pick up and deliver side-by-sides anywhere in New Mexico for a fee. Find your city below.")}
<section class="section">
  <div class="wrap">
    <p class="sub">NM UTV is located at {ADDR_LINE}. Choose your city to learn about UTV repair, Polaris and Can-Am service, and pickup and delivery in your area.</p>
    {all_cities_html()}
  </div>
</section>"""
    page("utv-repair/index.html", "New Mexico UTV Repair Service Areas | NM UTV",
         "UTV and side-by-side repair for every New Mexico city, from Albuquerque and Las Cruces to Farmington and Hobbs. Shop in Socorro with statewide pickup & delivery.",
         body, schemas=[business_schema(), breadcrumb_schema(crumbs)], priority="0.9")


def build_services():
    crumbs = [("Home", "/"), ("Services", "/services/")]
    body = f"""{crumbs_html(crumbs)}
{hero("UTV &amp; Side-by-Side Repair Services",
      "From radios to engine swaps, NM UTV handles every kind of side-by-side repair at our Socorro, NM shop.")}
<section class="section"><div class="wrap">{service_cards()}</div></section>"""
    page("services/index.html", "UTV Repair Services | Engine, Suspension, Belts, Tires | NM UTV",
         "UTV repair services in Socorro, NM: engine repair and swaps, suspension, CVT belts and clutches, tires and wheels, crash repair, radio installs and more.",
         body, schemas=[business_schema(), breadcrumb_schema(crumbs)], priority="0.9")

    top = ["Albuquerque", "Las Cruces", "Los Lunas", "Belen", "Rio Rancho", "Santa Fe",
           "Truth or Consequences", "Socorro", "Roswell", "Farmington", "Alamogordo", "Silver City"]
    for s in SERVICES:
        crumbs = [("Home", "/"), ("Services", "/services/"), (s["name"], f'/services/{s["slug"]}/')]
        bullets = "".join(f"<li>{escape(b)}</li>" for b in s["bullets"])
        cities = "".join(f'<li><a href="{city_url(n)}">{escape(n)}</a></li>' for n in top)
        others = "".join(f'<li><a href="/services/{o["slug"]}/">{escape(o["short"])}</a></li>'
                         for o in SERVICES if o["slug"] != s["slug"])
        body = f"""{crumbs_html(crumbs)}
{hero(escape(s["name"]), escape(s["intro"]))}
<section class="section">
  <div class="wrap split">
    <div class="prose">
      <h2>What's included</h2>
      <ul class="checks">{bullets}</ul>
      <h2>Every major brand</h2>
      <p>We provide {escape(s["short"].lower())} for Polaris RZR XP 1000, RZR Pro XP, RZR 900, Ranger and General, Can-Am Maverick X3, Maverick R, Commander and Defender, Honda Talon and Pioneer, Kawasaki KRX, Yamaha YXZ and Wolverine, CFMOTO and Textron side-by-sides.</p>
      {model_chips()}
      <h2>Why NM UTV</h2>
      <p>{OWNER_BLURB}</p>
      <h2>Serving all of New Mexico</h2>
      <p>Our shop is in Socorro, and we offer UTV pickup and delivery statewide for a fee. Popular areas:</p>
      <ul class="chips">{cities}<li><a href="/utv-repair/">All cities</a></li></ul>
    </div>
    <div>
      {location_box()}
      <div class="side-list"><p class="loc-h">Other services</p><ul class="link-list">{others}</ul></div>
    </div>
  </div>
</section>"""
        page(f'services/{s["slug"]}/index.html', f'{s["name"]} | Socorro, NM | NM UTV',
             f'{s["name"]} at NM UTV in Socorro, New Mexico. {s["intro"].split(". ")[0]}. Statewide pickup & delivery. Call {PHONE}.'[:300],
             body, schemas=[business_schema(), breadcrumb_schema(crumbs),
                            {"@context": "https://schema.org", "@type": "Service", "name": s["name"],
                             "provider": {"@id": BUSINESS_ID},
                             "areaServed": {"@type": "State", "name": "New Mexico"}}],
             priority="0.8")


def build_models():
    crumbs = [("Home", "/"), ("Models", "/models/")]
    brands = []
    for m in MODELS:
        if m["brand"] not in brands:
            brands.append(m["brand"])
    groups = "".join(f'<div class="region"><h3>{escape(b)} repair</h3>{model_chips(b)}</div>' for b in brands)
    body = f"""{crumbs_html(crumbs)}
{hero("UTV Models We Repair",
      "Polaris, Can-Am, Honda, Kawasaki, Yamaha, CFMOTO and Arctic Cat side-by-sides, all repaired at our Socorro, NM shop.")}
<section class="section"><div class="wrap"><div class="regions">{groups}</div></div></section>"""
    page("models/index.html", "UTV Models We Repair | Polaris RZR, Can-Am X3 & More | NM UTV",
         "Side-by-side models repaired at NM UTV in Socorro: Polaris RZR XP 1000, RZR 900, Ranger, Can-Am Maverick X3, Defender, Honda Talon, Yamaha YXZ and more.",
         body, schemas=[business_schema(), breadcrumb_schema(crumbs)], priority="0.9")

    top = ["Socorro", "Albuquerque", "Las Cruces", "Los Lunas", "Belen", "Rio Rancho", "Santa Fe",
           "Truth or Consequences", "Roswell", "Farmington", "Alamogordo", "Gallup", "Hobbs", "Carlsbad", "Clovis", "Silver City"]
    for m in MODELS:
        crumbs = [("Home", "/"), ("Models", "/models/"), (f'{m["name"]} Repair', f'/models/{m["slug"]}/')]
        work = "".join(f"<li>{escape(w)}</li>" for w in m["work"])
        city_links = "".join(f'<li><a href="{city_url(n)}">{escape(n)} {escape(m["short"])} repair</a></li>' for n in top)
        aliases = ", ".join(m["aliases"])
        services = "".join(f'<li><a href="/services/{s["slug"]}/">{escape(s["short"])}</a></li>' for s in SERVICES)
        related = "".join(f'<li><a href="/models/{o["slug"]}/">{escape(o["name"])}</a></li>'
                          for o in MODELS if o["brand"] == m["brand"] and o["slug"] != m["slug"])
        faqs = [
            (f'Where can I get my {m["name"]} repaired in New Mexico?',
             f'NM UTV repairs the {m["name"]} at our shop at {ADDR_LINE}, and we offer pickup and delivery anywhere in New Mexico for a fee.'),
            (f'What {m["short"]} repairs do you do?', "We handle " + "; ".join(w.lower() for w in m["work"]) + "."),
            (f'How fast can you fix my {m["short"]}?',
             "Our turnaround is quick. Routine service, belts and accessory installs are typically fast, and we give you a clear timeline after diagnosing larger repairs."),
        ]
        body = f"""{crumbs_html(crumbs)}
{hero(f'{escape(m["name"])} Repair &amp; Service', escape(m["summary"]), eyebrow=f'{escape(m["brand"])} · Socorro, NM · Statewide pickup')}
<section class="section">
  <div class="wrap split">
    <div class="prose">
      <h2>{escape(m["short"])} repair work we do</h2>
      <ul class="checks">{work}</ul>
      <p>Whether you searched for {escape(aliases)}, you are in the right place. Our certified mechanics work on the {escape(m["name"])} regularly and keep the parts that wear out most in mind for New Mexico heat, sand, rock and altitude.</p>
      <h2>Why bring your {escape(m["short"])} to NM UTV</h2>
      <p>{OWNER_BLURB}</p>
      <h2>{escape(m["short"])} repair across New Mexico</h2>
      <p>We are located in Socorro and pick up and deliver side-by-sides statewide for a fee.</p>
      <ul class="chips">{city_links}</ul>
    </div>
    <div>
      {location_box()}
      <div class="side-list"><p class="loc-h">Services</p><ul class="link-list">{services}</ul></div>
      {f'<div class="side-list"><p class="loc-h">Other {escape(m["brand"])} models</p><ul class="link-list">{related}</ul></div>' if related else ''}
    </div>
  </div>
</section>
{faq_html(faqs, f'{escape(m["short"])} repair FAQ')}"""
        page(f'models/{m["slug"]}/index.html', f'{m["name"]} Repair | Socorro, NM UTV Shop | NM UTV',
             f'{m["name"]} repair in New Mexico: {", ".join(m["work"][:3]).lower()} and more. Socorro shop with statewide pickup & delivery. Call {PHONE}.',
             body, schemas=[business_schema(), breadcrumb_schema(crumbs), faq_schema(faqs)], priority="0.8")


def build_about():
    crumbs = [("Home", "/"), ("About", "/about/")]
    body = f"""{crumbs_html(crumbs)}
{hero("About NM UTV", "A Socorro, New Mexico UTV shop built on racing experience.")}
<section class="section">
  <div class="wrap split">
    <div class="prose">
      <h2>Meet the owner: {SITE['owner']}</h2>
      <p>{OWNER_BLURB}</p>
      <h2>Our mechanics</h2>
      <p>Every mechanic at NM UTV is certified and has been working on side-by-sides and powersports equipment for a long time. We work on Polaris, Can-Am, Honda, Kawasaki, Yamaha, CFMOTO and Arctic Cat/Textron machines every day.</p>
      <h2>How we work</h2>
      <ul class="checks">
        <li><strong>Diagnose first.</strong> We find the real cause so the problem doesn't come back.</li>
        <li><strong>Upfront pricing.</strong> You approve the work before we start.</li>
        <li><strong>Quick turnaround.</strong> We know you want to get back to riding or working.</li>
        <li><strong>Statewide pickup and delivery.</strong> Available anywhere in New Mexico for a fee.</li>
      </ul>
      <h2>What we do</h2>
      <p>We do everything from installing new radios to engine work, swapping engines, suspension work, new tires, new wheels, belt installations, crash repairs and much more.</p>
    </div>
    {location_box()}
  </div>
</section>"""
    page("about/index.html", "About NM UTV | Owned by Former Factory Can-Am Racer Dillon Zimmerman",
         "NM UTV in Socorro, NM is owned by Dillon Zimmerman, a former factory Can-Am ATV racing team member. Certified mechanics, fast turnaround and fair prices.",
         body, schemas=[business_schema(), breadcrumb_schema(crumbs)], priority="0.7")


def build_contact():
    crumbs = [("Home", "/"), ("Contact", "/contact/")]
    body = f"""{crumbs_html(crumbs)}
{hero("Contact NM UTV", "Call, email or stop by the shop in Socorro. Ask about pickup and delivery anywhere in New Mexico.")}
<section class="section">
  <div class="wrap split">
    <div class="prose">
      <h2>Get in touch</h2>
      <p><strong>Phone:</strong> <a href="tel:{TEL}">{PHONE}</a><br>
      <strong>Email:</strong> <a href="mailto:{EMAIL}">{EMAIL}</a><br>
      <strong>Shop:</strong> {ADDR_LINE}</p>
      <p>When you call, let us know the year, make and model of your side-by-side, what's going on with it, and whether you need pickup and delivery. Pickup and delivery is available anywhere in New Mexico for a fee.</p>
      <p><a class="btn" href="{MAP_LINK}" target="_blank" rel="noopener">Get directions</a></p>
      <div class="map"><iframe title="NM UTV location map" src="{MAP_EMBED}" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe></div>
    </div>
    {location_box()}
  </div>
</section>"""
    page("contact/index.html", "Contact NM UTV | UTV Repair in Socorro, NM | 575-418-0601",
         f"Contact NM UTV at {ADDR_LINE}. Call {PHONE} or email {EMAIL} for UTV repair, pickup and delivery anywhere in New Mexico.",
         body, schemas=[business_schema(), breadcrumb_schema(crumbs)], priority="0.7")


def build_404():
    body = f"""{hero("Page not found", "That page doesn't exist, but we can still fix your UTV.")}
<section class="section"><div class="wrap">{all_cities_html()}</div></section>"""
    before = len(SITEMAP)
    page("404.html", "Page Not Found | NM UTV", "Page not found.", body)
    del SITEMAP[before:]


def build_sitemap():
    urls = "".join(
        f"<url><loc>{u}</loc><lastmod>{TODAY}</lastmod><priority>{p}</priority></url>\n" for u, p in SITEMAP
    )
    with open(os.path.join(ROOT, "sitemap.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")
    with open(os.path.join(ROOT, "robots.txt"), "w") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")


if __name__ == "__main__":
    build_home()
    build_areas_hub()
    for c in CITIES:
        build_city(c)
    build_services()
    build_models()
    build_about()
    build_contact()
    build_404()
    build_sitemap()
    print(f"Built {len(SITEMAP)} pages")
