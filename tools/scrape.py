#!/usr/bin/env python3
"""Einmaliger Abzug von www.nicolasschuetzinger.com (Wix) nach data/ und site/img/.

Aufruf:  python3 tools/scrape.py            (alles)
         python3 tools/scrape.py --no-images (nur Daten und Texte)

Liest pro Seite die Galerie-Daten, die Wix im HTML mitliefert (Titel, Angaben,
Maße, Reihenfolge), und die Textblöcke. Bilder kommen in zwei Größen über
Wix' eigene Größen-URL: thumb (lange Kante 800px) und large (2000px).
"""
import html
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IMG = ROOT / "site" / "img"
BASE = "https://www.nicolasschuetzinger.com/"
MEDIA = "https://static.wixstatic.com/media/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
SIZES = {"thumb": 800, "large": 2000}
EXTRA_FILE = pathlib.Path(__file__).resolve().parent / "extra-items.json"
EXTRA = json.loads(EXTRA_FILE.read_text()) if EXTRA_FILE.exists() else {}

# Wix-Slug -> Name im Menü. Reihenfolge = Reihenfolge im ART-Menü.
PAGES = [
    ("", "ART"),
    ("painting", "PAINTING"),
    ("abstract-painting", "ABSTRACT PAINTING"),
    ("illustration", "ILLUSTRATION"),
    ("abstract-graphic", "ABSTRACT GRAPHIC"),
    ("drawing", "DRAWING"),
    ("graphic", "GRAPHIC"),
    ("erotic", "EROTIC"),
    ("leonce-lena", "LEONCE & LENA"),
    ("body", "BODY"),
    ("animation", "ANIMATION"),
    ("projects-7", "OBJECT"),
    ("comercial", "COMERCIAL"),
    ("vita", "VITA"),
    ("kontakt-1", "CONTACT"),
    ("press", "PRESS"),
    ("events", "EVENTS"),
    ("terms-conditions", "terms & conditions"),
]


def fetch(url, tries=3):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if n == tries - 1:
                raise
            print("   Wiederholung:", e)
            time.sleep(2)


def slugify(text):
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = text.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


def find_gallery(node):
    """Erste Galerie (…_galleryData) in Wix' Warmup-Daten samt Komponenten-ID."""
    if isinstance(node, dict):
        for key, val in node.items():
            if key.endswith("_galleryData") and isinstance(val, dict) and val.get("items"):
                return key[: -len("_galleryData")], val
            found = find_gallery(val)
            if found:
                return found
    elif isinstance(node, list):
        for val in node:
            found = find_gallery(val)
            if found:
                return found
    return None


def find_item(node, item_id):
    """Einzelnes Bild (…_directFullscreenItem) aus der Direktlink-Seite."""
    if isinstance(node, dict):
        if node.get("itemId") == item_id and "mediaUrl" in node:
            return node
        node = list(node.values())
    if isinstance(node, list):
        for val in node:
            found = find_item(val, item_id)
            if found:
                return found
    return None


def page_ids(page_html):
    """Wix-pageId -> Slug, um die Bildlinks der Startseite aufzulösen."""
    out = {}
    for m in re.finditer(r'"pageId":"([a-z0-9]+)","title":"[^"]*","pageUriSEO":"([^"]*)"', page_html):
        out[m.group(1)] = m.group(2)
    for m in re.finditer(r'"([a-z0-9]{5})":\{"pageId":"\1","title":"[^"]*","pageUriSEO":"([^"]*)"', page_html):
        out[m.group(1)] = m.group(2)
    return out


def clean_rich_text(inner):
    """Wix-Klassen entfernen, Auszeichnung und Inline-Stile behalten."""
    inner = re.sub(r'\sclass="([^"]*)"', lambda m: _keep_font_class(m.group(1)), inner)
    inner = re.sub(r'\s(?:data-[a-z-]+|dir|role|aria-[a-z-]+)="[^"]*"', "", inner)
    return inner.strip()


def _keep_font_class(classes):
    fonts = [c for c in classes.split() if re.fullmatch(r"font_\d+", c)]
    return ' class="%s"' % " ".join(fonts) if fonts else ""


def text_blocks(page_html):
    start, end = page_html.find("<main"), page_html.find("</main>")
    main = page_html[start:end]
    blocks = []
    for m in re.finditer(
        r'<div id="(comp-[a-z0-9]+)" class="[^"]*wixui-rich-text[^"]*"[^>]*>(.*?)</div>', main, re.S
    ):
        blocks.append({"id": m.group(1), "html": clean_rich_text(m.group(2))})
    return blocks


def image_url(name, w, h, long_edge):
    scale = min(1.0, long_edge / max(w, h))
    tw, th = max(1, round(w * scale)), max(1, round(h * scale))
    out_name = name.rsplit(".", 1)[0] + ".jpg"  # Endung des letzten Teils bestimmt das Format
    return "%s%s/v1/fit/w_%d,h_%d,q_85/%s" % (MEDIA, name, tw, th, out_name)


def make_item(n, it):
    md = it.get("metaData", {})
    name = it["mediaUrl"]
    ext = "jpg"  # auch PNG-Quellen kommen als JPEG (keine hat Transparenz, spart ~90 %)
    title = (md.get("title") or "").strip()
    stem = slugify(title) or slugify(pathlib.Path(md.get("fileName") or "bild").stem) or "bild"
    link = md.get("link") or {}
    return {
        "file": "%02d-%s.%s" % (n, stem, ext),
        "title": title,
        "description": (md.get("description") or "").strip(),
        "alt": (md.get("alt") or "").strip(),
        "width": md.get("width"),
        "height": md.get("height"),
        "wix_id": it.get("itemId"),
        "wix_media": name,
        "link_page_id": (link.get("data") or {}).get("pageId", "").lstrip("#"),
    }


def main():
    with_images = "--no-images" not in sys.argv
    DATA.mkdir(exist_ok=True)
    pages, id_map, total = [], {}, 0

    for slug, label in PAGES:
        key = slug or "home"
        print("Seite:", key)
        page_html = fetch(BASE + slug).decode("utf-8", "replace")
        id_map.update(page_ids(page_html))
        entry = {"slug": slug, "key": key, "label": label, "blocks": text_blocks(page_html), "items": []}

        m = re.search(r'<script type="application/json" id="wix-warmup-data">(.*?)</script>', page_html, re.S)
        gallery = find_gallery(json.loads(m.group(1))) if m else None
        if gallery:
            entry["gallery_id"] = gallery[0]
            raw_items = list(gallery[1]["items"])
            # Wix liefert höchstens 25 Bilder mit; der Rest kommt über den Direktlink je Bild.
            for item_id in EXTRA.get(key, []):
                url = "%s%s?pgid=%s-%s" % (BASE, slug, gallery[0].replace("comp-", ""), item_id)
                m2 = re.search(r'<script type="application/json" id="wix-warmup-data">(.*?)</script>',
                               fetch(url).decode("utf-8", "replace"), re.S)
                hit = find_item(json.loads(m2.group(1)), item_id) if m2 else None
                if hit:
                    raw_items.append(hit)
                else:
                    print("   FEHLT:", key, item_id)
                time.sleep(0.2)
            for n, it in enumerate(raw_items, 1):
                entry["items"].append(make_item(n, it))
        pages.append(entry)
        time.sleep(0.3)

    for entry in pages:
        for it in entry["items"]:
            pid = it.pop("link_page_id")
            if pid:
                it["link"] = id_map.get(pid, "?" + pid)
        (DATA / (entry["key"] + ".json")).write_text(
            json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        if not with_images:
            continue
        for it in entry["items"]:
            for size, edge in SIZES.items():
                target = IMG / entry["key"] / size / it["file"]
                if target.exists() and target.stat().st_size > 0:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(fetch(image_url(it["wix_media"], it["width"], it["height"], edge)))
                total += 1
                time.sleep(0.1)
        print("  Bilder:", entry["key"], len(entry["items"]))

    print("Fertig. Seiten: %d, neu geladene Bilddateien: %d" % (len(pages), total))
    unresolved = [it["link"] for e in pages for it in e["items"] if str(it.get("link", "")).startswith("?")]
    if unresolved:
        print("Nicht aufgelöste Startseiten-Links:", unresolved)


if __name__ == "__main__":
    main()
