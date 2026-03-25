# Satellite Image AI Backend

Production-ready FastAPI backend for satellite image semantic segmentation and Gemini AI analysis.

## ✨ Features

### 1. **Semantic Segmentation** (`POST /predict`)
- Accepts satellite images (JPG, PNG, TIF)
- Runs ResNet50-UNet model inference
- Returns segmentation mask as base64-encoded PNG
- Model loads once at startup (no per-request overhead)

### 2. **AI Analysis Pipeline** (`POST /analyze`)
- 3-step Gemini pipeline:
  1. **Image Analysis**: Classify image and extract features (Gemini Vision)
  2. **Improvement Suggestions**: Generate recommendations (Gemini Text)
  3. **Image Generation**: Create enhanced satellite image (Gemini 2.0 Image Gen)
- Returns JSON with classification, features, description, improvements, and generated image

### 3. **Health Check** (`GET /health`)
- Verify model and Gemini API availability

---

## 🚀 Setup

### Prerequisites
- Python 3.12+
- Virtual environment (already configured)
- Gemini API key (from [Google AI Studio](https://aistudio.google.com))

### 1. Install Dependencies

From the `backend/` directory:

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Edit `backend/.env` and add your Gemini API key:

```env
GEMINI_API_KEY=your_actual_api_key_here
GEMINI_VISION_MODEL=gemini-1.5-flash
GEMINI_TEXT_MODEL=gemini-1.5-flash
GEMINI_IMAGE_MODEL=gemini-2.0-flash-exp-image-generation
MODEL_INPUT_SIZE=256
MODEL_NUM_CLASSES=23
CORS_ALLOW_ORIGINS=*
LOG_LEVEL=INFO
```

### 3. Place Model Weights

Download/obtain your `unet.weights.h5` and place it in the `backend/` directory:

```
backend/
  unet.weights.h5    ← Must exist here
  main.py
  model.py
  ...
```

---

## 🏃 Launch Server

### From Backend Directory

```bash
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

**Server running at:** `http://127.0.0.1:8001`

**Interactive API docs:** `http://127.0.0.1:8001/docs`

### Expected Startup Output

```
INFO:     Uvicorn running on http://127.0.0.1:8001
Loading segmentation model...
✓ Loaded weights from ./unet.weights.h5
✓ Model warmed up
Segmentation model is ready
```

---

## 📡 API Endpoints

### 1. Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "gemini_configured": true
}
```

---

### 2. Semantic Segmentation
```http
POST /predict
Content-Type: multipart/form-data

file: <image>
```

**Supported formats:** JPG, PNG, TIF (max 15 MB)

**Response:**
```json
{
  "mask_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "mask_mime_type": "image/png"
}
```

**Example cURL:**
```bash
curl -X POST \
  -F "file=@satellite_image.jpg" \
  http://127.0.0.1:8001/predict
```

---

### 3. Gemini Analysis Pipeline
```http
POST /analyze
Content-Type: multipart/form-data

file: <image>
```

**Response:**
```json
{
  "classification": "Urban development zone",
  "features": [
    "High-rise buildings",
    "Road networks",
    "Parks and green spaces",
    "Water bodies"
  ],
  "description": "Dense urban area with mixed residential and commercial development...",
  "improvements": [
    "Add green belts between buildings",
    "Improve water drainage systems",
    "Create dedicated cycling lanes"
  ],
  "generated_image": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Example cURL:**
```bash
curl -X POST \
  -F "file=@satellite_image.jpg" \
  http://127.0.0.1:8001/analyze
```

---

## 📁 Project Structure

```
backend/
├── main.py                          # FastAPI app, endpoints, lifespan
├── model.py                         # UNet architecture & weight loading
├── .env                             # Environment variables (API key, config)
├── requirements.txt                 # Python dependencies
├── unet.weights.h5                  # Model weights (place here)
├── services/
│   ├── __init__.py
│   └── gemini_service.py            # Gemini API integration (3 async functions)
├── schemas/
│   ├── __init__.py
│   └── response_schema.py           # Pydantic response models
└── utils/
    ├── __init__.py
    └── image_utils.py               # Image validation, preprocessing, encoding
```

---

## 🔐 Security & Best Practices

✅ **Implemented:**
- API key stored in environment variables (not hardcoded)
- File size limit: 15 MB
- File type validation (MIME + extension)
- Image integrity verification
- CORS configured
- Async error handling with proper HTTP status codes
- Logging for debugging
- Model warm-up to avoid first-request latency
- Thread-pooling for synchronous inference (doesn't block async loop)

---

## 📊 Error Handling

| Status | Error | Reason |
|--------|-------|--------|
| 400 | Bad Request | Invalid file, unsupported format, empty upload |
| 413 | Payload Too Large | File exceeds 15 MB limit |
| 500 | Internal Server Error | Model inference failure |
| 502 | Bad Gateway | Gemini API error or misconfiguration |

---

## 🔧 Configuration

### Model Parameters
Edit `.env` to change model behavior:
```env
MODEL_INPUT_SIZE=256      # Input resolution
MODEL_NUM_CLASSES=23      # Number of segmentation classes
```

### Gemini Models
Swap models in `.env`:
```env
GEMINI_VISION_MODEL=gemini-1.5-pro        # For better accuracy
GEMINI_IMAGE_MODEL=gemini-2.0-flash       # Available image gen model
```

### Logging
```env
LOG_LEVEL=INFO    # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

---

## 🧪 Testing with Python

```python
import requests
import base64

# Health check
response = requests.get("http://127.0.0.1:8001/health")
print(response.json())

# Upload image for segmentation
with open("satellite_image.jpg", "rb") as f:
    response = requests.post(
        "http://127.0.0.1:8001/predict",
        files={"file": f}
    )
    mask_b64 = response.json()["mask_base64"]
    
# Upload image for Gemini analysis
with open("satellite_image.jpg", "rb") as f:
    response = requests.post(
        "http://127.0.0.1:8001/analyze",
        files={"file": f}
    )
    result = response.json()
    print(f"Classification: {result['classification']}")
    print(f"Features: {result['features']}")
    print(f"Improvements: {result['improvements']}")
```

---

## ⚙️ Advanced

### Running in Production

```bash
# Use gunicorn with uvicorn workers
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001
```

### Environment Customization

```bash
# Custom port
uvicorn main:app --port 9000

# Custom host
uvicorn main:app --host 0.0.0.0

# SSL/HTTPS
uvicorn main:app --ssl-keyfile=key.pem --ssl-certfile=cert.pem
```

---

## 🐛 Troubleshooting

### Model weights not found
```
RuntimeError: Model weights not found at ./unet.weights.h5
```
**Solution:** Place `unet.weights.h5` in the `backend/` directory

### Gemini API key missing
```
HTTPException: Gemini API error: GEMINI_API_KEY is not configured
```
**Solution:** Set `GEMINI_API_KEY` in `.env`

### Image validation fails
- Ensure file has valid MIME type (image/jpeg, image/png, image/tiff)
- File size must be < 15 MB
- Image must be a valid image file (not corrupted)

### Slow first request
- Model warm-up happens at startup. First request should be normal speed.
- If slow, increase `MODEL_INPUT_SIZE` only if GPU available.

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| FastAPI | Web framework |
| Uvicorn | ASGI server |
| Google Gemini client library | Gemini API access |
| Pydantic | Request/response validation |
| python-dotenv | Environment loading |
| httpx | Async HTTP client (Gemini API) |
| Pillow | Image processing |

---

## 📝 License

Internal use only.

---

## ✅ Checklist Before Deployment

- [ ] `unet.weights.h5` exists in `backend/`
- [ ] `.env` has valid `GEMINI_API_KEY`
- [ ] All dependencies installed: `pip install -r requirements.txt`
- [ ] `/health` endpoint returns `status: ok`
- [ ] Test `/predict` with sample image
- [ ] Test `/analyze` with sample image
- [ ] Logs show no errors during startup
