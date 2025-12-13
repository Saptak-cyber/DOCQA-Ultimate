# Frontend Setup Guide

## Quick Start

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Create environment file:**
   ```bash
   cp .env.local.example .env.local
   ```

4. **Update `.env.local` with your backend URL:**
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

5. **Start the development server:**
   ```bash
   npm run dev
   ```

6. **Open your browser:**
   Navigate to [http://localhost:3000](http://localhost:3000)

## First Time Setup

### 1. Create an Account
- Go to `/signup`
- Enter your email and password
- Click "Sign Up"

### 2. Upload a Document
- Navigate to `/upload`
- Drag and drop a PDF file or click to select
- Wait for processing to complete

### 3. Query Your Documents
- Navigate to `/query`
- Type your question
- Get AI-powered answers with citations!

## Troubleshooting

### Backend Connection Issues
- Ensure your FastAPI backend is running on `http://localhost:8000`
- Check that CORS is configured correctly in your backend
- Verify `NEXT_PUBLIC_API_URL` in `.env.local`

### Authentication Issues
- Clear browser localStorage if you encounter auth errors
- Check that JWT_SECRET matches between frontend and backend

### Build Errors
- Delete `node_modules` and `.next` folder
- Run `npm install` again
- Check Node.js version (requires 18+)

## Production Build

```bash
npm run build
npm run start
```

## Project Structure

- `app/` - Next.js pages and layouts
- `components/` - Reusable React components
- `lib/` - Utilities, API clients, hooks, context
- `types/` - TypeScript type definitions
- `styles/` - Global CSS and Tailwind styles
