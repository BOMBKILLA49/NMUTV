# NMUTV — nmutv.com

Static site for NM UTV (UTV & side-by-side repair, Socorro, NM), hosted on GitHub Pages.

- Edit content/cities/models/services in `build/data.py` (page templates in `build/build.py`)
- Rebuild: `python3 build/build.py` — regenerates all HTML, `sitemap.xml` and `robots.txt`
- Commit and push; GitHub Pages serves the repo root (`CNAME` = nmutv.com)
