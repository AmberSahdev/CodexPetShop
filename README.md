# Codex Pet Shop

A community library of animated desktop pets for Codex. Anyone can post a pet (no account needed). Each pet gets a public page at `/p/<name>`.

Live: <https://codexpetshop.uc.r.appspot.com> (or wherever you deployed it).

---

## What's running where

| Concern | Where it lives | Notes |
|---|---|---|
| Web app | App Engine Standard, F1, Python 3.12 | Auto-scales 0–4. `app.yaml` controls everything. |
| Pet metadata (id, displayName, description, timestamps, takedown flag, ip_hash) | **Firestore (Native mode)**, collection `pets`, doc id = pet name | Free up to 50k reads + 20k writes/day. |
| `spritesheet.webp` files | **Cloud Storage**, bucket `codexpetshop-pets`, prefix `spritesheets/` | Public read; written only by the App Engine service account. |
| Auto-generated 200×200 PNG thumbnails | Same bucket, prefix `screenshots/` | Generated server-side from the top-left of the spritesheet. |
| Server logs (every request, every traceback) | App Engine logs (Cloud Logging) | Retained per Cloud Logging defaults. |

The store layer is a thin facade ([store.py](store.py)) that swaps backends based on the `CPS_BACKEND` env var:

- `CPS_BACKEND=local` → [local_store.py](local_store.py): JSON file at `data/pets.json` + files under `data/spritesheets/` and `data/screenshots/`. Default for dev.
- `CPS_BACKEND=gcp` → [cloud_store.py](cloud_store.py): Firestore + GCS. Set in [app.yaml](app.yaml) for production.

---

## Pet cap

There's a **hard cap of 1000 pets** ([config.py](config.py): `MAX_PETS = 1000`). Once the cap is hit, `POST /upload` returns `503 The shop is full…` and `ingest.py` refuses new pets.

Why the cap exists:
- Every homepage load currently does one Firestore scan that returns every visible pet (`grid_pets` in [cloud_store.py](cloud_store.py)). At 1000 pets that's 1000 reads per pageload.
- 50k Firestore reads/day = ~50 pageviews/day at the cap before paying. Anything bigger needs the indexed-query path or an in-process cache (see "Scaling beyond 1000" below).
- Storage and bandwidth are negligible until many thousands of pets.

To raise the cap, change `MAX_PETS` in [config.py](config.py) and redeploy. Before doing that, read "Scaling beyond 1000" below.

---

## Where data is stored

### Firestore — pet metadata

Database: `(default)` in **Native mode** in project `codexpetshop`.

Collection: `pets`. Document id = the pet's name (lowercase, the URL slug).

Each doc looks like:
```json
{
  "id": "ruckus",
  "display_name": "Ruckus",
  "description": "A friendly little guy.",
  "spritesheet_filename": "ruckus.webp",
  "screenshot_filename": "ruckus.png",
  "random": 0.42,
  "created_at": 1735689600.0,
  "ip_hash": "ab12cd34…",
  "takedown": false
}
```

Set `takedown: true` to hide a pet from the grid (it 404s on the detail page too). Documents are never auto-deleted.

### Cloud Storage — pet binaries

Bucket: `gs://codexpetshop-pets` (public read, App Engine SA writes).

Layout:
```
spritesheets/<id>.webp     ← original upload, ≤ 2 MB
screenshots/<id>.png        ← server-cropped 200×200 PNG thumbnail
```

Public URLs (used directly in `<img>` tags):
```
https://storage.googleapis.com/codexpetshop-pets/spritesheets/<id>.webp
https://storage.googleapis.com/codexpetshop-pets/screenshots/<id>.png
```

Cache headers: `cache-control: public, max-age=31536000, immutable`.

### Local dev

`CPS_BACKEND=local` (the default) writes to:
```
data/pets.json
data/spritesheets/<id>.webp
data/screenshots/<id>.png
```

`data/` is gitignored.

---

## Reviewing & managing uploads

### Browse pets (Firestore console)

<https://console.cloud.google.com/firestore/databases/-default-/data/panel/pets?project=codexpetshop>

Shows every doc, lets you edit fields inline, delete, or run ad-hoc queries.

CLI:
```bash
gcloud firestore documents list --collection-ids=pets --limit=50
```

### Browse files (GCS console)

<https://console.cloud.google.com/storage/browser/codexpetshop-pets?project=codexpetshop>

CLI:
```bash
gcloud storage ls -l gs://codexpetshop-pets/spritesheets/
gcloud storage ls -l gs://codexpetshop-pets/screenshots/
gcloud storage cp gs://codexpetshop-pets/screenshots/<id>.png /tmp/
```

### See who uploaded what

App Engine logs every request with source IP. Cross-reference an offensive pet's `ip_hash` (in Firestore) with `POST /upload` lines in the logs:

```bash
gcloud app logs read --limit=500 --service=default | grep "POST /upload"
```

Or in the console:
<https://console.cloud.google.com/logs/query;query=resource.type%3D%22gae_app%22%20AND%20httpRequest.requestMethod%3D%22POST%22?project=codexpetshop>

The `ip_hash` field is `sha256(IP + CPS_IP_SALT)[:32]`. Salt lives in `app.yaml` (gitignored).

### Take a pet down

**Hide only** (instant, free, reversible):
```bash
# Firestore console: open pets/<id>, set takedown = true
# Or CLI:
gcloud firestore documents update pets/<id> --update-mask=takedown --field=takedown=true
```

**Hard delete** (frees storage too):
```bash
gcloud firestore documents delete pets/<id>
gcloud storage rm gs://codexpetshop-pets/spritesheets/<id>.webp
gcloud storage rm gs://codexpetshop-pets/screenshots/<id>.png
```

---

## Security posture

| | Status |
|---|---|
| HTTPS enforced | ✅ `secure: always` in `app.yaml` |
| App Engine sandbox, read-only disk | ✅ |
| Pet name regex (`^[a-z0-9-]{2,24}$`) — no path traversal | ✅ |
| `pet.json` validated against strict jsonschema ([pet_schema.py](pet_schema.py)) | ✅ |
| Spritesheet validated as WebP via Pillow before storage | ✅ |
| Screenshot is server-generated, not user-supplied | ✅ |
| Service account has minimum roles | ✅ `datastore.user` + `storage.objectAdmin` on one bucket |
| Hard pet cap (1000) | ✅ |
| Per-IP rate limit | ❌ TODO |
| Content moderation (NSFW filter) | ❌ TODO — Cloud Vision SafeSearch on screenshots is the cheap fix |
| Billing budget alert | ❌ TODO — see DEPLOY.md |
| CSP / additional security headers | ❌ TODO |

If your domain ends up indexed and traffic spikes, the missing rate limit is the biggest concern. ~15 lines of Firestore-counter code can fix it.

---

## How uploads flow

1. Client (`/upload`) picks a name → `GET /api/check/<id>` confirms it's free.
2. Client drops a folder → JS extracts `pet.json` + `spritesheet.webp`, validates client-side.
3. Submit → `POST /upload` (multipart).
4. Server validates: cap, name regex, pet.json schema, WebP magic bytes, dimensions.
5. Server crops top-left 200×200 of the spritesheet → PNG thumbnail (`make_thumbnail` in [app.py](app.py)).
6. Server uploads spritesheet + thumbnail to GCS, writes pet doc to Firestore (transactional create — duplicate names are rejected).
7. Server returns `{ ok: true, redirect: "/p/<id>" }` → client navigates.

Bundle download (`/p/<id>/bundle.zip`) reconstructs `pet.json` from Firestore on demand and zips it with the spritesheet pulled from GCS.

---

## Local dev

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py        # → http://localhost:5000
```

Default backend is local — writes go to `data/`. To smoke-test the GCP backend locally against the real cloud:

```bash
gcloud auth application-default login
CPS_BACKEND=gcp \
  CPS_BUCKET=codexpetshop-pets \
  GOOGLE_CLOUD_PROJECT=codexpetshop \
  .venv/bin/python app.py
```

To bulk-import a folder of pets locally, drop directories under `data/incoming/<id>/` (each containing `pet.json` + `spritesheet.webp`) and run:

```bash
.venv/bin/python ingest.py            # ingest everything
.venv/bin/python ingest.py ruckus     # ingest just one
```

---

## Deployment

See [DEPLOY.md](DEPLOY.md) for the full one-time setup. After that, every deploy is just:

```bash
gcloud app deploy --quiet
```

Roll back to a previous version:
```bash
gcloud app versions list --service=default
gcloud app services set-traffic default --splits=<OLDER_VERSION>=1
```

---

## Costs

For ≤1000 pets and modest traffic:
- App Engine F1: free up to 28 instance-hours/day
- Firestore: free up to 50k reads + 20k writes/day
- Cloud Storage: 5 GB free; ~$0.02/GB/month after
- Egress: 1 GB/day free

**Practical ceiling on the free tier:** ~50 home-page views/day at cap, or many more at lower pet counts. Monitor at <https://console.cloud.google.com/billing>.

---

## Scaling beyond 1000 pets

Two cheap upgrades, in priority order:

1. **In-process cache for the grid query.** Cache `list_visible()` for 60 s. Result: ≤1 Firestore scan per minute per instance regardless of pageviews. Caps cost at any pet count.

2. **Indexed random sampling.** The earlier `grid_pets` design used `where("random", ">=", threshold).order_by("random").limit(N)` — that needs a composite index but reads only ~`N` docs per pageload (instead of all of them). The composite index was already created during deploy and is sitting unused. Restore that query path when you have ≥a few thousand pets.

Both changes are ~10 lines each. Don't bother until you actually hit the limits.

---

## File map

```
app.py              Flask routes + upload validation + thumbnail generator
config.py           Limits, paths, MAX_PETS, FEATURED_PETS list
store.py            Backend dispatcher (local vs gcp)
local_store.py      JSON file + filesystem backend (dev)
cloud_store.py      Firestore + GCS backend (prod)
pet_schema.py       jsonschema for pet.json
ingest.py           CLI: pull folders from data/incoming/ into the store
migrate.py          One-shot copy from local store → cloud store
templates/          Jinja templates
static/             CSS + upload.js (CDN-Tailwind, no build step)
app.yaml            App Engine config (env vars, scaling, HTTPS)
.gcloudignore       Files NOT uploaded by `gcloud app deploy`
DEPLOY.md           One-time GCP setup
README.md           This file
```
