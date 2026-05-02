# Deploying codexpetshop to App Engine

One-time setup, then `gcloud app deploy` thereafter.

## 0. Prereqs

- A Google Cloud project (free tier is plenty)
- `gcloud` CLI installed and logged in: `gcloud auth login`

```bash
export PROJECT=your-project-id          # ← change me
export REGION=us-central                 # App Engine region; pick once, can't change
export BUCKET=${PROJECT}-codexpetshop    # public GCS bucket for sprites/screenshots
gcloud config set project $PROJECT
```

## 1. Enable APIs

```bash
gcloud services enable \
  appengine.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com
```

## 2. Create App Engine app + Firestore (Native mode)

```bash
gcloud app create --region=$REGION
gcloud firestore databases create --location=$REGION --type=firestore-native
```

## 3. Create the public GCS bucket

```bash
gcloud storage buckets create gs://$BUCKET --location=$REGION --uniform-bucket-level-access
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=allUsers --role=roles/storage.objectViewer
```

## 4. Grant the App Engine service account access

```bash
SA=$PROJECT@appspot.gserviceaccount.com
gcloud projects add-iam-policy-binding $PROJECT \
  --member=serviceAccount:$SA --role=roles/datastore.user
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$SA --role=roles/storage.objectAdmin
```

## 5. Configure `app.yaml`

Edit [app.yaml](app.yaml):
- `CPS_BUCKET`: set to your bucket name (e.g. `your-project-id-codexpetshop`)
- `CPS_IP_SALT`: paste a fresh random hex (`python -c "import secrets; print(secrets.token_hex(16))"`)

`GOOGLE_CLOUD_PROJECT` is set automatically by App Engine — no need to specify.

## 6. Deploy

```bash
gcloud app deploy
gcloud app browse
```

Subsequent deploys: just `gcloud app deploy`.

## Local dev still works

`store.py` dispatches on `CPS_BACKEND`. Default is `local` (filesystem + JSON). Run:

```bash
.venv/bin/python app.py
```

To smoke-test the cloud backend locally (uses your `gcloud auth application-default login` creds):

```bash
gcloud auth application-default login
CPS_BACKEND=gcp CPS_BUCKET=$BUCKET GOOGLE_CLOUD_PROJECT=$PROJECT .venv/bin/python app.py
```

## Migrating existing pets (local → cloud)

If you've already added pets locally and want to push them to the cloud backend:

```bash
gcloud auth application-default login
CPS_BACKEND=gcp CPS_BUCKET=$BUCKET GOOGLE_CLOUD_PROJECT=$PROJECT .venv/bin/python migrate.py
```

(See `migrate.py`.)

## Costs

For low traffic this fits inside Google's free tier:
- App Engine: F1 instance with auto-scale to 0
- Firestore: ~50k reads/day free
- Cloud Storage: 5 GB free (a 200 KB pet costs ~$0.000005/month)
