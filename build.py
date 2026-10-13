#!/usr/bin/env python3
"""Baut die statische Seite nach site/ aus data/ und templates/.

Aufruf:  python3 build.py

Braucht nur die Python-Standardbibliothek. Bilder liegen bereits in site/img/
(siehe tools/scrape.py); dieses Skript schreibt nur die HTML-Dateien.
"""
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
SITE = ROOT / "site"
TPL = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")

NAME = "Nicolas Schützinger"
ASSET_VERSION = "2"  # bei jeder CSS/JS-Änderung hochzählen, sonst zeigt der Browser die alte Datei

# Reihenfolge = Reihenfolge im Menü. ART ist die Startseite, die Galerien hängen darunter.
ART = ["painting", "abstract-painting", "illustration", "abstract-graphic", "drawing", "graphic",
       "erotic", "leonce-lena", "body", "animation", "projects-7", "comercial"]
TOP = ["vita", "kontakt-1", "press", "events"]
ALL = ["home"] + ART + TOP + ["terms-conditions"]

ICONS = {
    "facebook": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 21v-8h2.7l.4-3.2H14V7.7c0-.9.3-1.6 1.6-1.6h1.7V3.2C17 3.1 16 3 14.9 3 12.5 3 10.8 4.5 10.8 7.3v2.5H8V13h2.8v8z"/></svg>',
    "instagram": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.6" y="3.6" width="16.8" height="16.8" rx="4.6" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="3.9" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="16.9" cy="7.1" r="1.1"/></svg>',
}


def load(key):
    return json.loads((DATA / (key + ".json")).read_text(encoding="utf-8"))


def esc(text):
    return html.escape(text or "", quote=True)


def url(root, slug):
    return root + (slug + "/" if slug else "")


def nav_html(pages, key, root):
    in_art = key == "home" or key in ART
    subs = "".join(
        '<li><a href="%s"%s>%s</a></li>' % (url(root, pages[k]["slug"]),
                                           ' class="current"' if k == key else "", esc(pages[k]["label"]))
        for k in ART
    )
    out = ['<li class="has-sub"><a href="%s"%s>ART</a>'
           '<button class="sub-toggle" aria-label="Untermenü" aria-expanded="false"></button>'
           '<ul class="sub">%s</ul></li>' % (root or "./", ' class="current"' if in_art else "", subs)]
    for k in TOP:
        out.append('<li><a href="%s"%s>%s</a></li>' % (
            url(root, pages[k]["slug"]), ' class="current"' if k == key else "", esc(pages[k]["label"])))
    return "".join(out)


def gallery_html(page, layout, root, key):
    conf = layout["gallery"]
    is_home = conf["type"] == "grid"
    items = []
    for it in page["items"]:
        img_root = "%simg/%s/" % (root, key)
        thumb, large = img_root + "thumb/" + it["file"], img_root + "large/" + it["file"]
        alt = it["alt"] or it["title"].replace("\n", " ")
        img = ('<img src="%s" srcset="%s 800w, %s 2000w" sizes="50vw" width="%d" height="%d" alt="%s" '
               'loading="lazy" decoding="async">' % (thumb, thumb, large, it["width"], it["height"], esc(alt)))
        if is_home:
            items.append('<a class="g-item" href="%s" data-w="%d" data-h="%d">%s<span class="g-title">%s</span></a>'
                         % (url(root, it.get("link", "")), it["width"], it["height"], img, esc(it["title"])))
        else:
            items.append('<a class="g-item" href="%s" data-w="%d" data-h="%d" data-id="%s" data-title="%s" '
                         'data-desc="%s">%s</a>' % (large, it["width"], it["height"], pathlib.Path(it["file"]).stem,
                                                    esc(it["title"]), esc(it["description"]), img))
    return ('<div class="gallery gallery-%s" data-type="%s" data-desktop="%s" data-mobile="%s">%s</div>' % (
        conf["type"], conf["type"], esc(json.dumps(conf["desktop"])), esc(json.dumps(conf["mobile"])), "".join(items)))


def block_html(text):
    """Feste px-Schriftgrößen skalierbar machen (Handy-Ansicht verkleinert pro Block)."""
    text = re.sub(r"font-size:\s*([\d.]+)px", r"font-size:calc(\1px * var(--fs, 1))", text)
    return text.replace("<br>\n", "<br>").replace("\n<br>", "<br>")


def part_style(part):
    d, m = part["desktop"], part["mobile"]
    pairs = [("dt", d["top"]), ("dl", d["left"]), ("dw", d["width"]), ("mt", m["top"]), ("ml", m["left"]), ("mw", m["width"])]
    if "height" in d:
        pairs += [("dh", d["height"]), ("mh", m["height"])]
    if "scale" in part:
        pairs.append(("ms", part["scale"]))
    return ";".join("--%s:%s" % p for p in pairs)


def parts_html(page, layout, root, key):
    blocks = {b["id"]: b["html"] for b in page["blocks"]}
    out = []
    for part in layout["parts"]:
        style = part_style(part)
        if part["kind"] == "text":
            out.append('<div class="part text" style="%s">%s</div>' % (style, block_html(blocks[part["id"]])))
        elif part["kind"] == "video":
            out.append('<div class="part video" style="%s"><iframe src="https://www.youtube-nocookie.com/embed/%s" '
                       'title="Video" loading="lazy" allow="encrypted-media; picture-in-picture; fullscreen" '
                       'allowfullscreen></iframe></div>' % (style, part["youtube"]))
        elif part["kind"] == "social":
            links = "".join('<a href="%s" target="_blank" rel="noopener noreferrer" aria-label="%s">%s</a>'
                            % (esc(href), name.capitalize(), ICONS[name]) for name, href in part["links"])
            out.append('<div class="part social" style="%s">%s</div>' % (style, links))
        elif part["kind"] == "slider":
            imgs = []
            for it in page["items"]:
                img_root = "%simg/%s/" % (root, key)
                imgs.append(
                    '<a class="s-item" href="%s" data-w="%d" data-h="%d" data-id="%s" data-title="%s" data-desc="%s">'
                    '<img src="%s" width="%d" height="%d" alt="%s" loading="lazy" decoding="async"></a>' % (
                        img_root + "large/" + it["file"], it["width"], it["height"], pathlib.Path(it["file"]).stem,
                        esc(it["title"]), esc(it["description"]), img_root + "thumb/" + it["file"],
                        it["width"], it["height"], esc(it["alt"] or it["title"])))
            out.append('<div class="part slider" style="%s;--gd:%d;--gm:%d;--wd:%s;--wm:%s"><div class="s-track">%s</div>'
                       '<button class="s-prev" aria-label="Zurück" hidden></button>'
                       '<button class="s-next" aria-label="Weiter"></button></div>'
                       % (style, part["gap_d"], part["gap_m"], part["item_d"], part["item_m"], "".join(imgs)))
    return '<div class="parts" style="--bd:%d;--bm:%d">%s</div>' % (
        layout["bottom_desktop"], layout["bottom_mobile"], "".join(out))


def main():
    layouts = json.loads((DATA / "layout.json").read_text(encoding="utf-8"))
    pages = {k: load(k) for k in ALL}
    for key in ALL:
        page, layout = pages[key], layouts[key]
        root = "" if key == "home" else "../"
        if "gallery" in layout:
            body, kind = gallery_html(page, layout, root, key), "kind-gallery"
        else:
            body, kind = parts_html(page, layout, root, key), "kind-text"
        classes = "page-%s %s" % (key, kind)
        if "anchor_left" in layout:
            classes += " anchor-left"
        title = NAME if key == "home" else "%s | %s" % (page["label"], NAME)
        out = (TPL.replace("{{title}}", esc(title))
               .replace("{{root}}", root)
               .replace("{{home}}", root or "./")
               .replace("{{v}}", ASSET_VERSION)
               .replace("{{classes}}", classes)
               .replace("{{anchor}}", ' style="--anchor:%dpx"' % layout["anchor_left"] if "anchor_left" in layout else "")
               .replace("{{nav}}", nav_html(pages, key, root))
               .replace("{{terms}}", url(root, "terms-conditions"))
               .replace("{{main}}", body))
        target = SITE / page["slug"] / "index.html" if page["slug"] else SITE / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out, encoding="utf-8")
        print("gebaut:", target.relative_to(ROOT), "(%d Bilder)" % len(page["items"]))
    (SITE / ".nojekyll").write_text("")


if __name__ == "__main__":
    main()
