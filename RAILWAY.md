Deploying to Railway (step-by-step)

This project is prepared to deploy to Railway. Two methods: Buildpack (recommended) or Docker.

Prerequisites
- Create a Railway account and a new project (https://railway.app).

Option 1 — Railway Buildpack (quick)
1. Push your repo to GitHub (or connect your Git repo to Railway).
2. In Railway: New Project → Deploy from GitHub → choose this repository.
3. In Deploy options set environment variables under Settings:
   - `PORT` (Railway provides automatically)
   - Optional for GCS: `USE_GCS=true` and `GCS_BUCKET=your-bucket-name`
   - If using GCS with a service account JSON key, either attach the key as a Railway Secret and set `GOOGLE_APPLICATION_CREDENTIALS=/tmp/key.json`, or prefer Workloads Identity if available.
4. Railway will detect `requirements.txt` and use Python buildpack. `Procfile` starts the app.

Option 2 — Docker (use if you want custom image)
1. From repo root, build and push image:
   ```bash
   docker build -t registry.railway.app/<YOUR_PROJECT>/<IMAGE>:latest .
   docker push registry.railway.app/<YOUR_PROJECT>/<IMAGE>:latest
   ```
   (Railway may provide its own registry and docs.)
2. In Railway, choose Deploy → Container and point to the image.

Environment & GCS
- For GCS integration set `USE_GCS=true` and `GCS_BUCKET=your-bucket-name` in Railway project settings.
- To allow Railway to access your GCS bucket, create a service account with `Storage Object Admin`, download its JSON key, then add the key content as a Railway secret and set `GOOGLE_APPLICATION_CREDENTIALS` to the path where you write the key inside the container (e.g., `/secrets/gcs-key.json`).

Notes
- Railway sets `$PORT` automatically; Procfile uses it via Gunicorn.
- If you don't need GCS, skip those env vars — app will use local filesystem (ephemeral on Railway containers).

Troubleshooting
- Check logs in Railway dashboard for errors.
- Ensure `requirements.txt` is at repo root so buildpack installs dependencies.

GitHub Action: Auto-deploy on push
1. Create two repository secrets in GitHub: `RAILWAY_API_KEY` and `RAILWAY_PROJECT_ID`.
   - `RAILWAY_API_KEY`: your Railway API key (from account settings).
   - `RAILWAY_PROJECT_ID`: the Railway project id (found in the project settings).
2. A GitHub Action workflow `.github/workflows/deploy-railway.yml` is included in this repo. It runs on push to `main`.
3. The workflow installs the Railway CLI, authenticates using `RAILWAY_API_KEY`, then runs `railway up` for the specified `RAILWAY_PROJECT_ID`.

If you prefer to trigger deployments from Railway directly (connect GitHub in Railway), you can skip adding these secrets.

