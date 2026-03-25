import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from schemas.response_schema import AnalyzeResponse, HealthResponse
from services.gemini_service import GeminiServiceError, analyze_image, generate_image, get_improvements
from utils.image_utils import MAX_FILE_SIZE_BYTES, validate_upload

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "app.log"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("satellite-backend")


app = FastAPI(
    title="Satellite Image AI Backend",
    description="Gemini-only satellite analysis pipeline",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        gemini_configured=bool(os.getenv("GEMINI_API_KEY")),
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)) -> AnalyzeResponse:
    try:
        if file is None:
            raise HTTPException(status_code=400, detail="Missing file")

        image_bytes = await file.read()
        validate_upload(file, image_bytes, max_size_bytes=MAX_FILE_SIZE_BYTES)
        logger.info("Image received: filename=%s size_bytes=%d", file.filename, len(image_bytes))

        logger.info("Gemini step 1: analyze_image")
        step1 = await analyze_image(image_bytes)

        logger.info("Gemini step 2: get_improvements")
        step2 = await get_improvements(step1)

        logger.info("Gemini step 3: generate_image")
        generated_image = await generate_image(image_bytes, step2["improvements"])

        logger.info("Analyze completed successfully")
        return AnalyzeResponse(
            classification=step1["classification"],
            features=step1["features"],
            description=step1["description"],
            improvements=step2["improvements"],
            generated_image=generated_image,
        )
    except HTTPException:
        raise
    except GeminiServiceError as exc:
        logger.exception("Gemini pipeline failed")
        raise HTTPException(status_code=502, detail=f"Gemini API error: {exc}")
    except Exception:
        logger.exception("/analyze failed")
        raise HTTPException(status_code=500, detail="Internal server error")
