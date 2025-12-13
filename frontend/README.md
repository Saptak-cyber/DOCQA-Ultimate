# DOCQA Ultimate - Frontend

Next.js frontend for the DOCQA Ultimate document Q&A system.

## 🚀 Getting Started

### Prerequisites
- Node.js 18+ and npm/yarn
- Backend FastAPI server running on `http://localhost:8000`

### Installation

1. Install dependencies:
```bash
npm install
# or
yarn install
```

2. Create `.env.local` file:
```bash
cp .env.local.example .env.local
```

3. Update `.env.local` with your backend URL:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Development

Run the development server:
```bash
npm run dev
# or
yarn dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## 📁 Project Structure

```
frontend/
├── app/                    # Next.js App Router pages
├── components/            # React components
│   ├── ui/               # Base UI components
│   ├── layout/           # Layout components
│   ├── auth/             # Authentication components
│   ├── documents/        # Document management components
│   └── query/            # Query interface components
├── lib/                   # Utilities and configs
│   ├── api/              # API client functions
│   ├── context/          # React Context providers
│   ├── hooks/            # Custom React hooks
│   └── utils/            # Utility functions
└── types/                # TypeScript type definitions
```

## 🎨 Features

- ✅ User authentication (Login/Signup)
- ✅ Document upload with drag & drop
- ✅ Document list with real-time status updates
- ✅ Query interface with AI-powered answers
- ✅ Source citations with page numbers
- ✅ Responsive design
- ✅ Protected routes

## 🔧 Tech Stack

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Axios** - HTTP client
- **React Hook Form** - Form handling
- **React Dropzone** - File uploads
- **Lucide React** - Icons

## 📝 Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint

## 🔐 Authentication

The app uses JWT tokens stored in localStorage. Tokens are automatically included in API requests via Axios interceptors.

## 📡 API Integration

All API calls are made through the `lib/api` modules:
- `auth.ts` - Authentication endpoints
- `documents.ts` - Document management endpoints
- `query.ts` - Query endpoints

## 🎯 Pages

- `/` - Landing page
- `/login` - Login page
- `/signup` - Signup page
- `/documents` - Documents list (protected)
- `/upload` - Upload documents (protected)
- `/query` - Query interface (protected)
