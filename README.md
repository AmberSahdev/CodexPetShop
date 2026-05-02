# Codex Pet Shop

A community library of animated desktop pets for Codex.

Each pet gets a public page at `/p/<name>`.

## Local dev

Create the venv and install deps:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Run locally with the local JSON/filesystem store:

```bash
.venv/bin/python app.py
```

Open:

```bash
http://localhost:5000
```

## Run locally against the real GCP pets

First authenticate:

```bash
gcloud auth application-default login
```

Then export the ADC file path:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/application_default_credentials.json"
```

Then load the GCP env vars:

```bash
source scripts/use_gcp_local.sh
```

Then run the app:

```bash
.venv/bin/python app.py
```

So the full sequence is:

```bash
gcloud auth application-default login
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/application_default_credentials.json"
source scripts/use_gcp_local.sh
.venv/bin/python app.py
```

## What `scripts/use_gcp_local.sh` does

It exports:

```bash
CPS_BACKEND=gcp
GOOGLE_CLOUD_PROJECT=codexpetshop
CPS_BUCKET=codexpetshop-pets
CPS_COLLECTION=pets
CPS_CANONICAL_HOST=www.codexpetshop.com
```

You must `source` it, not run it directly:

```bash
source scripts/use_gcp_local.sh
```

## Notes

- Local default backend is `local`, which reads from `data/pets.json`
- Production uses the GCP backend from `app.yaml`
- If local looks empty, you are probably still on the local backend or `GOOGLE_APPLICATION_CREDENTIALS` is not set
