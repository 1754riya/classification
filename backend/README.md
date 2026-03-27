# Satellite Image AI Backend

Production-stage FastAPI backend for a strict staged pipeline:

1. `POST /upload`
2. `POST /improve`
3. `POST /generate`

The architecture is intentionally staged and stateful per `image_id`.

## Environment Variables

Create or edit `backend/.env`:

```env
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key

# Optional model overrides
GEMINI_VISION_MODEL=gemini-3-flash-preview
GEMINI_IMAGE_MODEL=gemini-2.5-flash
GROQ_MODEL=llama3-8b-8192

# App settings
CORS_ALLOW_ORIGINS=*
LOG_LEVEL=INFO
```

## Run Locally

From `backend/`:

```bash
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

Open docs at `http://127.0.0.1:8001/docs`.

## Endpoints

### `GET /health`

```json
{
  "status": "ok",
  "gemini_vision_configured": true,
  "gemini_image_configured": true,
  "gemini_shared_key_configured": true,
  "groq_configured": true
}
```

### `POST /upload`

Request:
- `multipart/form-data`
- field name: `file`
- allowed formats: JPG, PNG, TIF/TIFF

Response:

```json
{
  "image_id": "f2f7f30e-cc10-4f19-9f55-4f2c7fe57dd9",
  "classification": "Urban fringe",
  "features": [
    {
      "name": "Residential blocks",
      "coordinates": [132.0, 88.0, 240.0, 150.0]
    }
  ],
  "description": "Mixed built-up area with sparse vegetation."
}
```

### `POST /improve`

Request:

```json
{
  "image_id": "f2f7f30e-cc10-4f19-9f55-4f2c7fe57dd9"
}
```

Response:

```json
{
  "image_id": "f2f7f30e-cc10-4f19-9f55-4f2c7fe57dd9",
  "improvements": [
    "Add connected tree corridors",
    "Install rainwater harvesting zones"
  ]
}
```

### `POST /generate`

Request:

```json
{
  "image_id": "f2f7f30e-cc10-4f19-9f55-4f2c7fe57dd9"
}
```

Response:

```json
{
  "image_id": "f2f7f30e-cc10-4f19-9f55-4f2c7fe57dd9",
  "generated_image": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

## Full Curl Flow

Step 1: Upload image and capture `image_id`.

```bash
curl -X POST \
  -F "file=@sample.jpg" \
  http://127.0.0.1:8001/upload
```

Step 2: Generate improvements from step 1 output.

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"image_id":"<IMAGE_ID_FROM_UPLOAD>"}' \
  http://127.0.0.1:8001/improve
```

Step 3: Generate improved image.

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"image_id":"<IMAGE_ID_FROM_UPLOAD>"}' \
  http://127.0.0.1:8001/generate
```

## Error Handling

| Status | Case |
|--------|------|
| 400 | Missing file, empty upload, unsupported format, invalid image |
| 404 | Invalid or expired `image_id` |
| 409 | Stage order violation (`/improve` before `/upload`, `/generate` before `/improve`) |
| 413 | File exceeds size limit |
| 502 | Gemini or Groq upstream API failure |
| 504 | Upstream timeout |
| 500 | Unexpected internal error |

## Operational Notes

- Shared `httpx.AsyncClient` instances are reused for Gemini and Groq.
- Memory store is bounded by TTL + max item count + LRU eviction.
- Validation failures, retries, and memory evictions are logged to `backend/logs/app.log`.
