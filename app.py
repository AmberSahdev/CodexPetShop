import hashlib
import io
import json
import os
import re
import zipfile
from pathlib import Path
from urllib.parse import urljoin

from flask import (
    Flask, abort, jsonify, redirect, render_template,
    request, send_file, url_for,
)
from PIL import Image, UnidentifiedImageError

import config
import store
from pet_schema import validate_pet_json, clip_description

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = (
    config.MAX_SPRITESHEET_BYTES + config.MAX_SCREENSHOT_BYTES + 128 * 1024
)

ID_RE = re.compile(r"^[a-z0-9-]{2,24}$")
THUMB_SIZE = 200


def make_thumbnail(spritesheet_bytes: bytes) -> bytes:
    """Crop top-left THUMB_SIZE x THUMB_SIZE from the spritesheet.
    If smaller, crop what's there and upscale with NEAREST (preserves pixel art)."""
    with Image.open(io.BytesIO(spritesheet_bytes)) as im:
        im = im.convert("RGBA")
        w, h = im.size
        crop = im.crop((0, 0, min(THUMB_SIZE, w), min(THUMB_SIZE, h)))
        if crop.size != (THUMB_SIZE, THUMB_SIZE):
            crop = crop.resize((THUMB_SIZE, THUMB_SIZE), Image.NEAREST)
        out = io.BytesIO()
        crop.save(out, format="PNG", optimize=True)
        return out.getvalue()


@app.context_processor
def inject_globals():
    import datetime
    return {
        "now_year": datetime.datetime.utcnow().year,
        "icon": _icon,
        "absolute_url": _absolute_url,
        "canonical_request_url": _canonical_request_url,
    }


_ICONS_DIR = config.BASE_DIR / "static" / "icons"
_icon_cache: dict[str, tuple[int, str]] = {}


def _icon(name: str, cls: str = "") -> "Markup":
    """Inline an SVG from static/icons/<name>.svg, injecting Tailwind classes
    onto the root <svg> tag. Returns Markup so Jinja doesn't escape it."""
    from markupsafe import Markup
    path = _ICONS_DIR / f"{name}.svg"
    if path.exists():
        mtime_ns = path.stat().st_mtime_ns
        cached = _icon_cache.get(name)
        if not cached or cached[0] != mtime_ns:
            _icon_cache[name] = (mtime_ns, path.read_text())
        svg = _icon_cache[name][1]
    else:
        svg = ""
    if cls and svg:
        svg = svg.replace("<svg ", f'<svg class="{cls}" ', 1)
    return Markup(svg)


def _absolute_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        if request:
            return url.replace(request.host_url.rstrip("/"), _preferred_root().rstrip("/"), 1)
        return url
    return urljoin(_preferred_root(), url.lstrip("/"))


def _preferred_root() -> str:
    canonical_host = os.environ.get("CPS_CANONICAL_HOST", "www.codexpetshop.com")
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme if request else "https")
    return f"{scheme}://{canonical_host}/"


def _canonical_request_url() -> str:
    return urljoin(_preferred_root(), request.full_path.lstrip("/")).rstrip("?")


@app.before_request
def redirect_to_canonical_host():
    canonical_host = os.environ.get("CPS_CANONICAL_HOST", "www.codexpetshop.com")
    bare_host = canonical_host.removeprefix("www.")
    if request.host == bare_host:
        return redirect(_canonical_request_url(), code=301)


def _ip_hash(req) -> str:
    ip = req.headers.get("X-Forwarded-For", req.remote_addr or "").split(",")[0].strip()
    return hashlib.sha256((ip + config.IP_HASH_SALT).encode()).hexdigest()[:32]


@app.template_filter("relative_time")
def relative_time(ts: float) -> str:
    import time
    delta = max(0, time.time() - ts)
    if delta < 60: return "just now"
    if delta < 3600: return f"{int(delta // 60)}m ago"
    if delta < 86400: return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def _decorate(pet: dict) -> dict:
    """Attach spritesheet_url + screenshot_url so templates don't care about backend."""
    pet = dict(pet)
    pet["spritesheet_url"] = url_for("sprite_file", pet_id=pet["id"])
    pet["screenshot_url"] = (
        url_for("screenshot_file", pet_id=pet["id"])
        if pet.get("screenshot_filename")
        else None
    )
    return pet


@app.route("/")
def index():
    pets = [_decorate(p) for p in
            store.grid_pets(config.FEATURED_PETS, config.GRID_TOTAL, config.GRID_FEATURED_SLOTS)]
    featured_count = sum(1 for p in pets if p["id"] in config.FEATURED_PETS)
    return render_template("index.html", pets=pets, featured_count=featured_count)


PETS_PER_PAGE = 24


@app.route("/all")
def all_pets():
    all_sorted = sorted(
        (_decorate(p) for p in store.list_visible()),
        key=lambda p: p.get("created_at", 0),
    )
    total = len(all_sorted)
    total_pages = max(1, (total + PETS_PER_PAGE - 1) // PETS_PER_PAGE)
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    page = max(1, min(page, total_pages))
    start = (page - 1) * PETS_PER_PAGE
    pets = all_sorted[start : start + PETS_PER_PAGE]
    return render_template(
        "all.html",
        pets=pets,
        page=page,
        total_pages=total_pages,
        total=total,
        per_page=PETS_PER_PAGE,
        has_prev=page > 1,
        has_next=page < total_pages,
    )


@app.route("/upload", methods=["GET"])
def upload_form():
    return render_template("upload.html")


@app.route("/api/check/<pet_id>")
def api_check(pet_id: str):
    pet_id = pet_id.lower().strip()
    if not ID_RE.match(pet_id):
        return jsonify(available=False, reason="invalid"), 200
    return jsonify(available=not store.exists(pet_id)), 200


@app.route("/upload", methods=["POST"])
def upload_submit():
    if store.count_visible() >= config.MAX_PETS:
        return jsonify(
            error=f"The shop is full ({config.MAX_PETS} pets). New uploads are paused."
        ), 503

    name = (request.form.get("name") or "").lower().strip()
    pet_json_file = request.files.get("pet_json")
    sprite_file = request.files.get("spritesheet")

    if not name or not ID_RE.match(name):
        return jsonify(error="Invalid name. Use 2–24 chars: a–z, 0–9, hyphen."), 400
    if not pet_json_file:
        return jsonify(error="Missing pet.json (drop your pet folder)."), 400
    if not sprite_file:
        return jsonify(error="Missing spritesheet.webp (drop your pet folder)."), 400

    try:
        manifest = json.loads(pet_json_file.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return jsonify(error=f"pet.json is not valid JSON ({e})."), 400

    errors = validate_pet_json(manifest)
    if errors:
        return jsonify(error="pet.json failed validation: " + "; ".join(errors)), 400

    sprite_bytes = sprite_file.read()
    if len(sprite_bytes) > config.MAX_SPRITESHEET_BYTES:
        return jsonify(error="Spritesheet exceeds 10 MB."), 413
    if len(sprite_bytes) == 0:
        return jsonify(error="Spritesheet is empty."), 400

    try:
        with Image.open(io.BytesIO(sprite_bytes)) as im:
            im.verify()
        with Image.open(io.BytesIO(sprite_bytes)) as im:
            if im.format != "WEBP":
                return jsonify(error=f"Spritesheet must be WebP (got {im.format})."), 400
            if im.width > config.MAX_SPRITESHEET_DIM or im.height > config.MAX_SPRITESHEET_DIM:
                return jsonify(error=f"Spritesheet exceeds {config.MAX_SPRITESHEET_DIM}px."), 400
    except Exception as e:
        return jsonify(error=f"Spritesheet is not a valid image ({e})."), 400

    try:
        screenshot_bytes = make_thumbnail(sprite_bytes)
        screenshot_ext = "png"
    except Exception as e:
        return jsonify(error=f"Couldn't generate thumbnail ({e})."), 400

    try:
        store.create(
            pet_id=name,
            display_name=manifest["displayName"],
            description=clip_description(manifest["description"]),
            spritesheet_bytes=sprite_bytes,
            ip_hash=_ip_hash(request),
            screenshot_bytes=screenshot_bytes,
            screenshot_ext=screenshot_ext,
        )
    except ValueError as e:
        if str(e) == "name_taken":
            return jsonify(error=f'The name "{name}" is already taken.'), 409
        raise

    return jsonify(ok=True, redirect=url_for("pet_page", pet_id=name)), 200


@app.route("/healthz")
def healthz():
    return "ok", 200


@app.route("/sprites/<pet_id>.webp")
def sprite_file(pet_id: str):
    if not ID_RE.match(pet_id):
        abort(404)
    if not store.exists(pet_id):
        abort(404)
    data = store.spritesheet_bytes(pet_id)
    if not data:
        abort(404)
    return send_file(io.BytesIO(data), mimetype="image/webp", max_age=31536000)


@app.route("/screenshots/<pet_id>")
def screenshot_file(pet_id: str):
    if not ID_RE.match(pet_id):
        abort(404)
    pet = store.get(pet_id)
    if not pet:
        abort(404)
    data = store.screenshot_bytes(pet)
    if not data:
        abort(404)
    ext = (pet.get("screenshot_filename") or "").rsplit(".", 1)[-1].lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
    return send_file(io.BytesIO(data), mimetype=mime.get(ext, "application/octet-stream"), max_age=31536000)


@app.route("/p/<pet_id>/bundle.zip")
def pet_bundle(pet_id: str):
    pet_id = pet_id.lower()
    pet = store.get(pet_id)
    if not pet:
        abort(404)
    sprite_data = store.spritesheet_bytes(pet_id)
    if not sprite_data:
        abort(404)
    manifest = {
        "id": pet["id"],
        "displayName": pet["display_name"],
        "description": pet["description"],
        "spritesheetPath": "spritesheet.webp",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pet.json", json.dumps(manifest, indent=2))
        z.writestr("spritesheet.webp", sprite_data)
    buf.seek(0)
    try:
        store.bump_download(pet_id)
    except Exception as e:
        # Counter is best-effort: never fail the download because of it.
        app.logger.warning("bump_download failed for %s: %s", pet_id, e)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"{pet_id}.zip")


# Keep the pet page route near the end so it doesn't shadow other routes.
@app.route("/p/<pet_id>")
def pet_page(pet_id: str):
    pet_id = pet_id.lower()
    if not ID_RE.match(pet_id):
        abort(404)
    pet = store.get(pet_id)
    if not pet:
        abort(404)
    return render_template("pet.html", pet=_decorate(pet))


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="Upload too large (limit 10 MB)."), 413


if __name__ == "__main__":
    app.run(debug=True, port=5000)
