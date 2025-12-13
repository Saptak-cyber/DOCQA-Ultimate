# Backend Testing with Postman

Base URL (local): `http://localhost:8000`

## 1) Sign up (get a JWT)
- Method: `POST`
- URL: `http://localhost:8000/api/signup`
- Body (JSON):
  ```json
  { "email": "test@example.com", "password": "yourpassword" }
  ```
- Response: `{ "token": "<JWT>" }`

## 2) Login (get a JWT, if already registered)
- Method: `POST`
- URL: `http://localhost:8000/api/login`
- Body (JSON):
  ```json
  { "email": "test@example.com", "password": "yourpassword" }
  ```
- Response: `{ "token": "<JWT>" }`

Use this JWT as a Bearer token in subsequent requests:
- In Postman, set `Authorization` type to `Bearer Token` and paste the token.
- Or add a header: `Authorization: Bearer <JWT>`.

## 3) Upload a PDF (starts processing)
- Method: `POST`
- URL: `http://localhost:8000/api/upload`
- Auth: Bearer token from step 1 or 2.
- Body: `form-data`
  - Key: `file` (type = File), choose a PDF file.
- Response: `{"status": "queued", "document_id": "<id>" }`
- What happens:
  - File is stored to Supabase Storage.
  - A job is pushed to `queue:stage1` in Redis.
  - Workers process extraction → chunking → embedding → storage.

## 4) Check documents/status
- Method: `GET`
- URL: `http://localhost:8000/api/documents`
- Auth: Bearer token.
- Response: list of your documents with status (e.g., `uploaded`, `processing`, `indexed`).

## 5) Ask a question (not yet exposed)
- A `/api/query` route is **not currently implemented** in `app/main.py`. The retrieval logic exists in `app/retrieval.py` but isn’t wired to a FastAPI route. To test querying via Postman, an API route (e.g., `POST /api/query` that calls `ask_question`) must be added to the backend first.

## Notes
- Make sure your backend is running (`uvicorn app.main:app --reload --port 8000` or via Docker) and your workers/Redis are running so uploads get processed.
- If you change the frontend origin, set `FRONTEND_ORIGIN` in `.env` so CORS allows it.
