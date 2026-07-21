# Vercel Deployment Guide for P&ID Line List Tool

## Configuration Created
1. `vercel.json` has been configured to build and serve the Flask application using `@vercel/python`.
2. `requirements.txt` contains all required dependencies (`Flask`, `pandas`, `openpyxl`, `PyMuPDF`, `gunicorn`, `google-cloud-storage`).

## How to Deploy to Vercel

### Option 1: Deploy via Vercel CLI (Recommended)
Run the following command in your terminal inside the project directory:

```bash
npx vercel
```
- Follow the prompts to log in to your Vercel account and link the repository.
- To deploy to production, run:
```bash
npx vercel --prod
```

### Option 2: Deploy via GitHub Integration (Vercel Dashboard)
1. Push your latest code changes to your GitHub repository:
   ```bash
   git add .
   git commit -m "Add PDF OCR tool, verification screen, and Vercel configuration"
   git push origin main
   ```
2. Go to [Vercel Dashboard](https://vercel.com/new).
3. Select your repository (`pid-line-tool`).
4. Click **Deploy**. Vercel will automatically detect `vercel.json` and build the Flask Python serverless app.
