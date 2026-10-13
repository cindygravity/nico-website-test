#!/usr/bin/env python3
"""„Website bearbeiten" — lokaler Bearbeitungsmodus für die Seite.

Start:  Doppelklick auf „Website bearbeiten.command" (oder: python3 admin/server.py)
Optionen: --no-push  (Veröffentlichen committet nur lokal, lädt nichts hoch)
          --no-open  (Browser nicht öffnen)
          --port N

Läuft nur auf diesem Rechner (127.0.0.1). Liefert die gebaute Seite aus site/ aus und
hängt lokal Bearbeitungs-Skript und -Stil an. In den gebauten Dateien steht davon nichts.
Braucht nur Python-Standardbibliothek, macOS `sips` (Bilder verkleinern) und `git`.
"""
import contextlib
import io
import json
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import threading
import unicodedata
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADMIN = ROOT / "admin"
SITE = ROOT / "site"
DATA = ROOT / "data"
ORIGINALS = ROOT / "originals"
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

TOKEN = secrets.token_urlsafe(24)
LOCK = threading.Lock()
NO_PUSH = "--no-push" in sys.argv
SIZES = (("large", 2000), ("thumb", 800))
PRIVATE = "private collection"
YEAR = re.compile(r"\d{4}([/-]\d{2,4})?")
DIMS = re.compile(r"\d+([.,]\d+)? ?x ?\d+([.,]\d+)?( ?x ?\d+([.,]\d+)?)? ?(cm)?", re.I)


def _identity():
    """Falls auf dem Rechner kein Git-Name hinterlegt ist, einen neutralen mitgeben, sonst scheitert das Speichern."""
    res = subprocess.run(["git", "-C", str(ROOT), "config", "user.email"], capture_output=True, text=True)
    return [] if res.stdout.strip() else ["-c", "user.name=Website", "-c", "user.email=website@localhost"]


IDENTITY = _identity()


class Problem(Exception):
    """Fehler, der Nico als Satz angezeigt wird."""


# ---------- Daten ----------

def editable_pages():
    """Galerien, in denen Bilder gepflegt werden (nicht Startseite, nicht Textseiten)."""
    layouts = json.loads((DATA / "layout.json").read_text(encoding="utf-8"))
    return {k for k, v in layouts.items() if v.get("gallery", {}).get("type") in ("rows", "columns", "fixed")}


def load(page):
    if page not in editable_pages():
        raise Problem("Diese Seite lässt sich hier nicht bearbeiten.")
    return json.loads((DATA / (page + ".json")).read_text(encoding="utf-8"))


def save(page, data):
    (DATA / (page + ".json")).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        build.main()


def parse_description(text):
    """Beschreibung -> Felder (Maße, Technik, Jahr, Privatsammlung). None, wenn sie nicht ins Muster passt."""
    lines = text.split("\n") if text else []
    fields = {"size": "", "technique": "", "year": "", "private": False}
    if lines and lines[-1] == PRIVATE:
        fields["private"] = True
        lines = lines[:-1]
    if lines and YEAR.fullmatch(lines[-1]):
        fields["year"] = lines[-1]
        lines = lines[:-1]
    if len(lines) == 2 and (fields["year"] or DIMS.fullmatch(lines[0])):
        fields["size"], fields["technique"] = lines
    elif len(lines) == 1:
        fields["size" if DIMS.fullmatch(lines[0]) else "technique"] = lines[0]
    elif lines:
        return None
    return fields if compose_description(fields) == (text or "") else None


def compose_description(fields):
    lines = [fields.get("size", "").strip(), fields.get("technique", "").strip(), fields.get("year", "").strip()]
    if fields.get("private"):
        lines.append(PRIVATE)
    return "\n".join(l for l in lines if l)


def techniques():
    """Bisher verwendete Techniken, häufigste zuerst (Vorschläge im Feld)."""
    count = {}
    for page in editable_pages():
        for it in json.loads((DATA / (page + ".json")).read_text(encoding="utf-8"))["items"]:
            fields = parse_description(it["description"])
            if fields and fields["technique"]:
                count[fields["technique"]] = count.get(fields["technique"], 0) + 1
    return sorted(count, key=lambda t: (-count[t], t))


def find(data, file):
    for it in data["items"]:
        if it["file"] == file:
            return it
    raise Problem("Dieses Bild gibt es nicht mehr. Bitte die Seite neu laden.")


# ---------- Bilder ----------

def slugify(text):
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue")):
        text = text.replace(a, b)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


def sips(*args):
    res = subprocess.run(["sips", *args], capture_output=True, text=True)
    if res.returncode != 0:
        raise Problem("Das Bild konnte nicht verarbeitet werden. Ist es eine Bilddatei (JPG, PNG, HEIC, TIFF)?")
    return res.stdout


def exif_orientation(path):
    """EXIF-Ausrichtung einer JPEG-Datei (1–8), 1 wenn keine da ist."""
    try:
        raw = path.read_bytes()[:200000]
        i = raw.find(b"Exif\x00\x00")
        if i < 0:
            return 1
        tiff = raw[i + 6:]
        order = "little" if tiff[:2] == b"II" else "big"
        ifd = int.from_bytes(tiff[4:8], order)
        for n in range(int.from_bytes(tiff[ifd:ifd + 2], order)):
            entry = tiff[ifd + 2 + n * 12: ifd + 14 + n * 12]
            if int.from_bytes(entry[:2], order) == 0x0112:
                return int.from_bytes(entry[8:10], order)
    except Exception:  # noqa: BLE001
        pass
    return 1


def add_image(page, filename, body):
    data = load(page)
    stem = slugify(pathlib.Path(filename).stem) or "bild"
    suffix = pathlib.Path(filename).suffix.lower() or ".jpg"
    taken = {it["file"] for it in data["items"]}
    name, n = stem + ".jpg", 2
    while name in taken or (SITE / "img" / page / "large" / name).exists():
        name, n = "%s-%d.jpg" % (stem, n), n + 1

    original = ORIGINALS / page / (pathlib.Path(name).stem + suffix)
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(body)

    targets = {size: SITE / "img" / page / size / name for size, _ in SIZES}
    try:
        for size, edge in SIZES:
            targets[size].parent.mkdir(parents=True, exist_ok=True)
            source = original if size == "large" else targets["large"]
            sips("-s", "format", "jpeg", "-s", "formatOptions", "85", "-Z", str(edge), str(source), "--out", str(targets[size]))
        out = sips("-g", "pixelWidth", "-g", "pixelHeight", str(targets["large"]))
        width = int(re.search(r"pixelWidth: (\d+)", out).group(1))
        height = int(re.search(r"pixelHeight: (\d+)", out).group(1))
    except Exception:
        for t in targets.values():
            t.unlink(missing_ok=True)
        original.unlink(missing_ok=True)
        raise
    if exif_orientation(targets["large"]) in (5, 6, 7, 8):  # Hochkant-Foto: der Browser dreht es, also Maße tauschen
        width, height = height, width

    data["items"].insert(0, {"file": name, "title": "", "description": "", "alt": "", "width": width, "height": height})
    save(page, data)
    return name


def update_item(page, payload):
    data = load(page)
    item = find(data, payload["file"])
    item["title"] = str(payload.get("title", item["title"])).strip()
    if isinstance(payload.get("fields"), dict):
        item["description"] = compose_description(payload["fields"])
    elif "description" in payload:
        item["description"] = "\n".join(l.rstrip() for l in str(payload["description"]).strip().split("\n"))
    save(page, data)
    return item


def reorder(page, files):
    data = load(page)
    by_file = {it["file"]: it for it in data["items"]}
    if sorted(files) != sorted(by_file):
        raise Problem("Die Reihenfolge passt nicht mehr zum Stand. Bitte die Seite neu laden.")
    data["items"] = [by_file[f] for f in files]
    save(page, data)


def delete_item(page, file):
    data = load(page)
    data["items"].remove(find(data, file))
    for size, _ in SIZES:
        (SITE / "img" / page / size / file).unlink(missing_ok=True)
    save(page, data)


# ---------- Stand, Verwerfen, Veröffentlichen ----------

def git(*args, check=True):
    res = subprocess.run(["git", "-C", str(ROOT), *IDENTITY, *args], capture_output=True, text=True)
    if check and res.returncode != 0:
        raise Problem("Git meldet einen Fehler: " + (res.stderr.strip().splitlines() or ["unbekannt"])[-1])
    return res


def status():
    """Offene Änderungen gegenüber dem zuletzt veröffentlichten Stand, in Nicos Begriffen."""
    added = removed = edited = moved = 0
    for page in sorted(editable_pages()):
        now = json.loads((DATA / (page + ".json")).read_text(encoding="utf-8"))["items"]
        old_raw = git("show", "HEAD:data/%s.json" % page, check=False)
        old = json.loads(old_raw.stdout)["items"] if old_raw.returncode == 0 else []
        old_by, now_by = {i["file"]: i for i in old}, {i["file"]: i for i in now}
        added += len(now_by.keys() - old_by.keys())
        removed += len(old_by.keys() - now_by.keys())
        shared = [f for f in now_by if f in old_by]
        edited += sum(1 for f in shared if (now_by[f]["title"], now_by[f]["description"]) != (old_by[f]["title"], old_by[f]["description"]))
        if [i["file"] for i in old if i["file"] in now_by] != shared:
            moved += 1
    parts = []
    if added:
        parts.append("%d neu" % added)
    if edited:
        parts.append("%d geändert" % edited)
    if removed:
        parts.append("%d gelöscht" % removed)
    if moved:
        parts.append("Reihenfolge")
    other = bool(git("status", "--porcelain", "--", "data", "site", check=False).stdout.strip())
    return {"count": added + removed + edited + moved, "text": ", ".join(parts), "dirty": other, "no_push": NO_PUSH}


def discard():
    git("checkout", "HEAD", "--", "data", "site")
    git("clean", "-fdq", "--", "data", "site")


def publish():
    with contextlib.redirect_stdout(io.StringIO()):
        build.main()
    st = status()
    git("add", "-A", "--", "data", "site")
    if git("diff", "--cached", "--quiet", check=False).returncode != 0:
        git("commit", "-q", "-m", "Website: " + (st["text"] or "Aktualisierung"))
    if NO_PUSH:
        return "Testmodus: gespeichert, aber nicht hochgeladen."
    res = git("push", "origin", "HEAD:main", check=False)
    if res.returncode != 0:
        err = res.stderr.lower()
        if "could not resolve host" in err or "unable to access" in err or "timed out" in err:
            raise Problem("Keine Verbindung zu GitHub. Die Änderungen sind gespeichert. Sobald das Internet wieder da ist, noch einmal auf „Veröffentlichen“ klicken.")
        if "authentication" in err or "denied" in err or "403" in err:
            raise Problem("GitHub hat den Zugang abgelehnt. Die Änderungen sind gespeichert. Der Zugang muss neu eingerichtet werden.")
        raise Problem("Hochladen fehlgeschlagen: " + (res.stderr.strip().splitlines() or ["unbekannt"])[-1])
    return "Hochgeladen. In etwa einer Minute ist es online."


def unpublished_commits():
    res = git("rev-list", "--count", "origin/main..HEAD", check=False)
    return int(res.stdout.strip() or 0) if res.returncode == 0 else 0


# ---------- Server ----------

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def page_key(self, path):
        first = path.strip("/").split("/")[0]
        return first or "home"

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)
        if url.path in ("/_admin/edit.js", "/_admin/edit.css"):
            body = (ADMIN / url.path.rsplit("/", 1)[1]).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/css" if url.path.endswith(".css") else "application/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if url.path == "/_admin/status":
            with LOCK:
                st = status()
                st["pending_upload"] = unpublished_commits()
            return self.send_json(st)
        if url.path == "/_admin/items":
            try:
                with LOCK:
                    data = load(query.get("page", [""])[0])
                    items = [dict(it, fields=parse_description(it["description"])) for it in data["items"]]
                    return self.send_json({"items": items, "techniques": techniques()})
            except Problem as e:
                return self.send_json({"error": str(e)}, 400)
        if url.path.startswith("/_admin/"):
            return self.send_error(404)

        target = pathlib.Path(self.translate_path(url.path))
        if target.is_dir():
            if not url.path.endswith("/"):
                self.send_response(301)
                self.send_header("Location", url.path + "/")
                self.end_headers()
                return
            target = target / "index.html"
        if target.suffix == ".html" and target.exists():
            key = self.page_key(url.path)
            conf = {"token": TOKEN, "page": key, "editable": key in editable_pages()}
            inject = ('<link rel="stylesheet" href="/_admin/edit.css">'
                      '<script>window.ADMIN=%s</script><script src="/_admin/edit.js" defer></script></head>' % json.dumps(conf))
            body = target.read_text(encoding="utf-8").replace("</head>", inject, 1).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)
        host = self.headers.get("Host", "").split(":")[0]
        if self.headers.get("X-Admin-Token") != TOKEN or host not in ("127.0.0.1", "localhost"):
            return self.send_json({"error": "Sitzung abgelaufen. Bitte die Seite neu laden."}, 403)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        try:
            with LOCK:
                if url.path == "/_admin/upload":
                    name = urllib.parse.unquote(self.headers.get("X-Filename", "bild.jpg"))
                    return self.send_json({"file": add_image(query.get("page", [""])[0], name, body)})
                payload = json.loads(body or b"{}")
                if url.path == "/_admin/item":
                    item = update_item(payload["page"], payload)
                    return self.send_json({"item": dict(item, fields=parse_description(item["description"]))})
                if url.path == "/_admin/order":
                    reorder(payload["page"], payload["files"])
                    return self.send_json({"ok": True})
                if url.path == "/_admin/delete":
                    delete_item(payload["page"], payload["file"])
                    return self.send_json({"ok": True})
                if url.path == "/_admin/discard":
                    discard()
                    return self.send_json({"ok": True})
                if url.path == "/_admin/publish":
                    return self.send_json({"message": publish()})
            self.send_error(404)
        except Problem as e:
            self.send_json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            self.send_json({"error": "Unerwarteter Fehler: %s" % e}, 500)


def main():
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8020
    if not shutil.which("sips"):
        print("Hinweis: `sips` fehlt (kein macOS?). Bilder hochladen geht dann nicht.")
    address = "http://127.0.0.1:%d/painting/" % port
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        print("Der Bearbeitungsmodus läuft schon. Ich öffne ihn im Browser.")
        webbrowser.open(address)
        return
    print("\n  Website bearbeiten läuft:  %s\n" % address)
    print("  Dieses Fenster offen lassen, solange du arbeitest.")
    print("  Zum Beenden: Fenster schließen.\n")
    if NO_PUSH:
        print("  TESTMODUS: Veröffentlichen lädt nichts hoch.\n")
    if "--no-open" not in sys.argv:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
