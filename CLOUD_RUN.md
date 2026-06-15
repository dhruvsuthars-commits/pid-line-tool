Deploying PID Line Tool to Google Cloud Run

Overview
- This repository contains a small Flask app in the `pid-line-tool` folder.
- This guide builds a Docker image and deploys it to Cloud Run (managed).
- Cloud Run has a free tier for low-traffic services; check GCP quotas for details.

Prerequisites
- Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install
- Authenticate: `gcloud auth login`
- Select a project with billing enabled (Cloud Run requires a project):
  `gcloud config set project PROJECT_ID`
- Enable required APIs: `gcloud services enable run.googleapis.com cloudbuild.googleapis.com`

Build & Deploy (recommended: source deploy)
1) From the repository root, deploy directly from source (Cloud Build will build container):

```bash
# Set region
REGION=us-central1

gcloud run deploy pid-line-tool \
  --source . \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --project PROJECT_ID
```

2) Or build and push image manually, then deploy

```bash
# Build image and push to Artifact Registry or Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/pid-line-tool:latest

# Deploy to Cloud Run
gcloud run deploy pid-line-tool \
  --image gcr.io/PROJECT_ID/pid-line-tool:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated
```

Environment & Files
- The app listens on `$PORT` (Cloud Run sets this automatically). The `Dockerfile` exposes `8080`.
- Persisted files (uploads/output) will be stored inside the container's filesystem which is ephemeral. For production use, configure Cloud Storage (GCS) and update the app to save/read from GCS buckets.

Notes on Free Tier
- Cloud Run provides a free tier allocation (CPU, memory & request quotas) per month; it is suitable for testing and low-traffic internal tools.
- If you expect sustained usage, enable logging/billing alerts to avoid unexpected charges.

Next steps I can do for you
- Add a `cloudbuild.yaml` for advanced builds
- Update the app to use GCS for uploads/outputs
- Add simple authentication (IAP / Cloud Run Auth / Flask-Login)

