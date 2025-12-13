# DOCQA Ultimate - Frontend Architecture Design

## 🏗️ Architecture Overview

### Tech Stack
- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **State Management**: React Context API + Custom Hooks
- **HTTP Client**: Axios
- **Form Handling**: React Hook Form
- **UI Components**: Custom components with Tailwind
- **Authentication**: JWT stored in localStorage + Context

---

## 📁 Project Structure

```
frontend/
├── app/                          # Next.js App Router
│   ├── layout.tsx               # Root layout with providers
│   ├── page.tsx                 # Landing/Home page
│   ├── (auth)/                  # Auth route group
│   │   ├── login/
│   │   │   └── page.tsx         # Login page
│   │   └── signup/
│   │       └── page.tsx        # Signup page
│   ├── (dashboard)/             # Protected route group
│   │   ├── layout.tsx          # Dashboard layout (sidebar, header)
│   │   ├── documents/
│   │   │   ├── page.tsx        # Documents list page
│   │   │   └── [id]/
│   │   │       └── page.tsx    # Document detail page
│   │   ├── upload/
│   │   │   └── page.tsx        # Upload document page
│   │   └── query/
│   │       └── page.tsx        # Query/chat interface
│
├── components/                   # Reusable components
│   ├── ui/                      # Base UI components
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Card.tsx
│   │   ├── Modal.tsx
│   │   ├── Spinner.tsx
│   │   ├── Badge.tsx
│   │   └── Alert.tsx
│   ├── layout/                  # Layout components
│   │   ├── Sidebar.tsx
│   │   ├── Header.tsx
│   │   ├── Footer.tsx
│   │   └── Navbar.tsx
│   ├── auth/                    # Auth components
│   │   ├── LoginForm.tsx
│   │   └── SignupForm.tsx
│   ├── documents/               # Document components
│   │   ├── DocumentList.tsx
│   │   ├── DocumentCard.tsx
│   │   ├── DocumentUpload.tsx
│   │   ├── DocumentStatus.tsx
│   │   └── DocumentDetail.tsx
│   └── query/                   # Query components
│       ├── QueryInterface.tsx
│       ├── QueryInput.tsx
│       ├── QueryResponse.tsx
│       ├── SourceList.tsx
│       └── SourceCard.tsx
│
├── lib/                         # Utilities and configs
│   ├── api/                     # API client
│   │   ├── client.ts            # Axios instance
│   │   ├── auth.ts              # Auth API calls
│   │   ├── documents.ts         # Documents API calls
│   │   └── query.ts             # Query API calls
│   ├── hooks/                   # Custom React hooks
│   │   ├── useAuth.ts           # Authentication hook
│   │   ├── useDocuments.ts      # Documents management hook
│   │   ├── useQuery.ts          # Query hook
│   │   └── useLocalStorage.ts   # LocalStorage hook
│   ├── context/                 # React Context providers
│   │   ├── AuthContext.tsx      # Auth state management
│   │   └── ThemeContext.tsx     # Theme management (optional)
│   └── utils/                   # Utility functions
│       ├── formatDate.ts
│       ├── formatFileSize.ts
│       └── constants.ts
│
├── types/                        # TypeScript types
│   ├── auth.ts
│   ├── document.ts
│   ├── query.ts
│   └── api.ts
│
├── styles/                       # Global styles
│   └── globals.css
│
├── public/                       # Static assets
│   ├── images/
│   └── icons/
│
├── tailwind.config.ts
├── tsconfig.json
├── next.config.js
├── package.json
└── .env.local                    # Environment variables
```

---

## 🎨 UI/UX Design

### Design System
- **Color Palette**:
  - Primary: Blue (600-700)
  - Success: Green (500-600)
  - Warning: Yellow (500-600)
  - Error: Red (500-600)
  - Neutral: Gray (50-900)
- **Typography**: Inter or System font stack
- **Spacing**: Tailwind's default scale (4px base)
- **Border Radius**: 8px (md), 12px (lg)
- **Shadows**: Subtle shadows for elevation

### Key Pages

#### 1. **Landing Page** (`/`)
- Hero section with value proposition
- Features overview
- Call-to-action buttons (Login/Signup)

#### 2. **Login Page** (`/login`)
- Clean form with email/password
- "Don't have an account?" link
- Error handling display

#### 3. **Signup Page** (`/signup`)
- Registration form
- Password strength indicator
- Terms & conditions checkbox

#### 4. **Dashboard Layout** (`/documents`, `/upload`, `/query`)
- **Sidebar Navigation**:
  - Documents
  - Upload
  - Query
  - Settings (optional)
  - Logout
- **Header**:
  - User email/avatar
  - Notifications (optional)
- **Main Content Area**: Page-specific content

#### 5. **Documents Page** (`/documents`)
- **Document List View**:
  - Grid/List toggle
  - Search/filter bar
  - Status badges (uploaded, processing, indexed, failed)
  - Upload date
  - Actions: View, Delete
- **Document Detail Modal**:
  - Title, status, upload date
  - Processing progress
  - Error messages (if failed)
  - Download link

#### 6. **Upload Page** (`/upload`)
- **Drag & Drop Zone**:
  - Large drop area
  - File input button
  - Supported formats info
  - Max file size indicator
- **Upload Progress**:
  - Progress bar
  - File name
  - Status updates
- **Upload History**: Recent uploads

#### 7. **Query Page** (`/query`)
- **Query Interface**:
  - Large text input/textarea
  - Submit button
  - Query history (optional)
- **Response Display**:
  - Answer section (markdown support)
  - Sources section:
    - Document title
    - Page number
    - Chunk text preview
    - Similarity score
    - Expandable full text
- **Loading States**: Spinner during query processing

---

## 🔐 Authentication Flow

```
1. User visits protected route
   ↓
2. Check localStorage for token
   ↓
3. If no token → Redirect to /login
   ↓
4. If token exists → Validate with backend
   ↓
5. If valid → Allow access
   ↓
6. If invalid → Clear token, redirect to /login
```

### Auth Context Structure
```typescript
{
  user: { email: string } | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => void
  isLoading: boolean
}
```

---

## 📡 API Integration

### API Client Setup
- Base URL: `process.env.NEXT_PUBLIC_API_URL` (default: `http://localhost:8000`)
- Axios instance with interceptors:
  - Request: Add `Authorization: Bearer {token}` header
  - Response: Handle 401 (unauthorized) → logout

### Endpoints Mapping

| Backend Endpoint | Frontend Function | Usage |
|-----------------|-------------------|-------|
| `POST /api/signup` | `signup(email, password)` | User registration |
| `POST /api/login` | `login(email, password)` | User authentication |
| `POST /api/upload` | `uploadDocument(file)` | Upload PDF |
| `GET /api/documents` | `getDocuments()` | List user documents |
| `POST /api/query` | `queryRAG(query, top_docs, top_chunks)` | Query documents |

---

## 🎯 Key Features

### 1. **Document Management**
- Upload PDFs with drag & drop
- Real-time status updates (polling or WebSocket)
- Document list with filtering
- Status indicators (uploaded → processing → indexed)
- Error handling and retry options

### 2. **Query Interface**
- Natural language query input
- Real-time response streaming (if backend supports)
- Source citations with page numbers
- Expandable source chunks
- Query history (localStorage)

### 3. **User Experience**
- Loading states for all async operations
- Error messages with actionable feedback
- Success notifications
- Responsive design (mobile-friendly)
- Dark mode support (optional)

---

## 🔄 State Management

### Global State (Context)
- **AuthContext**: User authentication state
- **ThemeContext**: UI theme preferences (optional)

### Local State (useState/useReducer)
- Form inputs
- UI toggles (modals, dropdowns)
- Component-specific data

### Server State (Custom Hooks)
- **useDocuments**: Document list, upload, status
- **useQuery**: Query submission, response handling

---

## 🚀 Implementation Phases

### Phase 1: Foundation
1. Next.js project setup
2. Tailwind CSS configuration
3. Base UI components
4. Layout components (Sidebar, Header)
5. Routing structure

### Phase 2: Authentication
1. Auth context setup
2. Login/Signup pages
3. Protected route middleware
4. API client with auth interceptors

### Phase 3: Document Management
1. Upload page with drag & drop
2. Documents list page
3. Document status polling
4. Document detail view

### Phase 4: Query Interface
1. Query input component
2. Query API integration
3. Response display with sources
4. Source expansion/collapse

### Phase 5: Polish
1. Error handling improvements
2. Loading states
3. Animations/transitions
4. Responsive design
5. Accessibility improvements

---

## 📦 Dependencies

```json
{
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0",
    "react-hook-form": "^7.48.0",
    "react-dropzone": "^14.2.0",
    "date-fns": "^2.30.0",
    "react-markdown": "^9.0.0",
    "lucide-react": "^0.294.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^18.2.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "eslint": "^8.54.0",
    "eslint-config-next": "^14.0.0"
  }
}
```

---

## 🔒 Security Considerations

1. **Token Storage**: localStorage (consider httpOnly cookies for production)
2. **XSS Protection**: Sanitize user inputs
3. **CSRF**: Use SameSite cookies if using cookies
4. **API URL**: Environment variables only
5. **Error Messages**: Don't expose sensitive backend details

---

## 🎨 Component Examples

### Document Status Badge
```tsx
<Badge 
  status={document.status} 
  // uploaded, processing, extracted, indexed, failed
/>
```

### Query Response
```tsx
<QueryResponse 
  answer={response.answer}
  sources={response.sources}
/>
```

### Upload Zone
```tsx
<DocumentUpload 
  onUpload={handleUpload}
  maxSize={10 * 1024 * 1024} // 10MB
  accept=".pdf"
/>
```

---

## 📱 Responsive Breakpoints

- **Mobile**: < 640px
- **Tablet**: 640px - 1024px
- **Desktop**: > 1024px

---

## 🎯 Next Steps

1. Review and approve architecture
2. Set up Next.js project
3. Implement Phase 1 (Foundation)
4. Iterate through remaining phases
5. Testing and refinement

---

This architecture provides a solid foundation for a modern, scalable, and user-friendly frontend for your DOCQA Ultimate system.
