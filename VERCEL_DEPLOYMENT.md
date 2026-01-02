# Vercel Deployment Guide for Frontend

This guide explains how to deploy your DOCQA Next.js frontend on Vercel.

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Repository**: Your code must be pushed to GitHub
3. **FastAPI Backend URL**: You'll need the URL from your Render deployment
4. **Environment Variables**: Frontend API endpoints and configuration

## Step 1: Push Frontend to GitHub

Make sure your frontend code is in a GitHub repository:

```bash
cd frontend
git init
git add .
git commit -m "Initial frontend commit"
git branch -M main
git remote add origin https://github.com/your-username/your-repo.git
git push -u origin main
```

## Step 2: Create Vercel Project

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **"Add New +"** → **"Project"**
3. Select **"Import Git Repository"**
4. Connect your GitHub account and select your repository
5. Configure:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: `./frontend` (if backend is at root)
   - **Build Command**: `npm run build` (usually auto-detected)
   - **Output Directory**: `.next` (usually auto-detected)
   - **Install Command**: `npm install` (usually auto-detected)

## Step 3: Add Environment Variables

1. In the Vercel project settings, go to **"Environment Variables"**
2. Add the following variables:

```
NEXT_PUBLIC_API_URL=https://docqa-ultimate.onrender.com
NEXT_PUBLIC_API_TIMEOUT=30000
```

**Important Notes:**
- Use `NEXT_PUBLIC_` prefix for variables that need to be accessible in the browser
- Replace `https://docqa-api.onrender.com` with your actual FastAPI backend URL
- Frontend environment variables are embedded in the bundle, so they're visible to clients

## Step 4: Deploy

1. Click **"Deploy"**
2. Vercel will:
   - Clone your repository
   - Install dependencies
   - Build your Next.js app
   - Deploy to their CDN

3. Your frontend will be available at: `https://your-project.vercel.app`

## Configuration Files

### .env.local (Local Development)

Create `frontend/.env.local` for local development:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_TIMEOUT=30000
```

### .env.production (Production - Vercel)

Create `frontend/.env.production` for production:

```
NEXT_PUBLIC_API_URL=https://docqa-api.onrender.com
NEXT_PUBLIC_API_TIMEOUT=30000
```

## Step 5: Update Backend CORS

After deploying your frontend, update the `FRONTEND_ORIGIN` environment variable on Render:

```
FRONTEND_ORIGIN=https://your-project.vercel.app
```

This ensures your backend accepts requests from your frontend domain.

## Updating Render Backend

If you haven't already, set the `GROQ_API_KEY` environment variable in Render:

1. Go to Render Dashboard
2. Select your `docqa-api` service
3. Go to **"Environment"**
4. Add/Update:
   ```
   GROQ_API_KEY=<your-groq-api-key>
   ```

5. Redeploy the service

## Environment Variables Summary

### Frontend (Vercel)

```
NEXT_PUBLIC_API_URL=https://docqa-api.onrender.com
NEXT_PUBLIC_API_TIMEOUT=30000
```

### Backend (Render)

```
GROQ_API_KEY=<your-groq-api-key>
FRONTEND_ORIGIN=https://your-project.vercel.app
MONGO_URI=<your-mongodb-uri>
REDIS_URL=<your-upstash-redis-url>
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-supabase-key>
SUPABASE_STORAGE_BUCKET=documents
JWT_SECRET=<your-jwt-secret>
WORKER_STAGE1_URL=https://worker-stage1.onrender.com/health
WORKER_STAGE2_URL=https://worker-stage2.onrender.com/health
WORKER_STAGE3_URL=https://worker-stage3.onrender.com/health
WORKER_STAGE4_URL=https://worker-stage4.onrender.com/health
```

## Automatic Deployments

Vercel automatically deploys when you push to your main branch:

```bash
git add .
git commit -m "Update feature"
git push origin main
# Vercel automatically detects and deploys
```

To disable auto-deployments, go to **Project Settings** → **Git** and toggle **"Auto-Deploy"**.

## Domain Configuration

### Custom Domain

1. Go to **Project Settings** → **Domains**
2. Click **"Add"**
3. Enter your custom domain (e.g., `app.example.com`)
4. Follow Vercel's DNS configuration instructions

### Default Vercel Domain

Your site is automatically available at: `https://your-project.vercel.app`

## Monitoring & Logs

1. Go to your Vercel project
2. Click **"Deployments"** to see build logs
3. Click **"Analytics"** to monitor performance
4. Click **"Functions"** to see serverless function logs

## API Calls from Frontend

The frontend uses `NEXT_PUBLIC_API_URL` to make API calls:

```typescript
// Example in frontend/lib/api/client.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = {
  get: (endpoint) => fetch(`${API_BASE}${endpoint}`),
  post: (endpoint, data) => fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  // ...
};
```

## Troubleshooting

### Build Fails

- Check Vercel build logs
- Ensure `npm run build` works locally
- Verify all dependencies are in `package.json`

### API Connection Issues

- Verify `NEXT_PUBLIC_API_URL` is set correctly
- Check CORS headers in FastAPI backend
- Ensure `FRONTEND_ORIGIN` matches your Vercel domain

### Cold Starts

- Vercel automatically optimizes Next.js for performance
- API routes and images are automatically optimized
- First request may be slower due to function startup

## Cost: $0/month

Vercel's free tier includes:
- 100 GB bandwidth/month
- Unlimited deployments
- Automatic SSL certificates
- CDN distribution

## Next Steps

1. Deploy frontend to Vercel
2. Update `FRONTEND_ORIGIN` in Render backend
3. Add `GROQ_API_KEY` to Render backend
4. Test full-stack integration
5. Monitor logs and analytics
