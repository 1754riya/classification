import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from services.gemini_service import (
    GeminiServiceError,
    analyze_image,
    close_gemini_client,
    generate_image,
)
from services.errors import UpstreamTimeoutError
from services.groq_service import GroqServiceError, close_groq_client, get_improvements
from schemas.response_schema import (
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    ImproveRequest,
    ImproveResponse,
    UploadResponse,
)
from storage.memory_store import ImageNotFoundError, StepOrderError, memory_store
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


# ISSUE 4 FIX: Proper CORS configuration with secure credentials handling
def _parse_cors_origins() -> tuple[str | list[str], bool]:
    """Parse CORS origins and determine allow_credentials setting.
    
    ISSUE 4 FIX:
    - If CORS_ALLOW_ORIGINS == "*", set allow_credentials = False (secure)
    - Otherwise, parse into list and set allow_credentials = True
    """
    cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    
    if cors_origins == "*":
        logger.info("CORS configured with allow_origins='*', credentials disabled")
        return "*", False
    
    origins_list = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
    logger.info("CORS configured with explicit origins: %s", origins_list)
    return origins_list, True


cors_origins, allow_creds = _parse_cors_origins()


# ISSUE 5 FIX: Use lifespan context manager to manage AsyncClient lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle and close shared clients on shutdown."""
    logger.info("Starting up: API initialized")
    yield
    logger.info("Shutting down: closing shared HTTP clients")
    await close_gemini_client()
    await close_groq_client()


app = FastAPI(
    title="Satellite Image AI Backend",
    description="User-driven step-by-step satellite AI pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    gemini_shared = bool(
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GEMINI_VISION_KEY")
        or os.getenv("GEMINI_IMAGE_KEY")
    )
    return HealthResponse(
        status="ok",
        gemini_vision_configured=bool(os.getenv("GEMINI_VISION_KEY")),
        gemini_image_configured=bool(os.getenv("GEMINI_IMAGE_KEY")),
        gemini_shared_key_configured=gemini_shared,
        groq_configured=bool(os.getenv("GROQ_API_KEY")),
    )


@app.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile | None = File(default=None)) -> UploadResponse:
    try:
        if file is None:
            raise HTTPException(status_code=400, detail="Missing file")

        logger.info("Upload received: POST /upload")
        image_bytes = await file.read()
        validate_upload(file, image_bytes, max_size_bytes=MAX_FILE_SIZE_BYTES)
        step1 = await analyze_image(image_bytes)
        image_id = await memory_store.create_entry(image_bytes=image_bytes, step1=step1)
        logger.info("Step 1 completed: image_id=%s classification=%s", image_id, step1["classification"])
        return UploadResponse(image_id=image_id, **step1)
    except HTTPException:
        raise
    except GeminiServiceError as exc:
        logger.exception("Gemini Step 1 failed")
        raise HTTPException(status_code=502, detail=f"Gemini API error: {exc}")
    except UpstreamTimeoutError as exc:
        logger.exception("Upstream timeout during Step 1")
        raise HTTPException(status_code=504, detail=f"Upstream timeout: {exc}")
    except Exception:
        logger.exception("/upload failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/improve", response_model=ImproveResponse)
async def improve(payload: ImproveRequest) -> ImproveResponse:
    try:
        step1 = await memory_store.get_step1(payload.image_id)
        step2 = await get_improvements(step1)
        await memory_store.save_step2(payload.image_id, step2)
        logger.info("Step 2 completed: image_id=%s improvements_count=%d", payload.image_id, len(step2["improvements"]))
        return ImproveResponse(image_id=payload.image_id, improvements=step2["improvements"])
    except ImageNotFoundError as exc:
        logger.warning("Step 2 failed: invalid image_id=%s", payload.image_id)
        raise HTTPException(status_code=404, detail=str(exc))
    except StepOrderError as exc:
        logger.warning("Step 2 failed: step order violation image_id=%s detail=%s", payload.image_id, str(exc))
        raise HTTPException(status_code=409, detail=str(exc))
    except GroqServiceError as exc:
        logger.exception("Groq Step 2 failed")
        raise HTTPException(status_code=502, detail=f"Groq API error: {exc}")
    except UpstreamTimeoutError as exc:
        logger.exception("Upstream timeout during Step 2")
        raise HTTPException(status_code=504, detail=f"Upstream timeout: {exc}")
    except Exception:
        logger.exception("/improve failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/generate", response_model=GenerateResponse)
async def generate(payload: GenerateRequest) -> GenerateResponse:
    try:
        image_bytes, improvements = await memory_store.get_for_generation(payload.image_id)
        generated_image = await generate_image(image_bytes, improvements)
        logger.info("Step 3 completed: image_id=%s generated_image_length=%d", payload.image_id, len(generated_image))
        return GenerateResponse(image_id=payload.image_id, generated_image=generated_image)
    except ImageNotFoundError as exc:
        logger.warning("Step 3 failed: invalid image_id=%s", payload.image_id)
        raise HTTPException(status_code=404, detail=str(exc))
    except StepOrderError as exc:
        logger.warning("Step 3 failed: step order violation image_id=%s detail=%s", payload.image_id, str(exc))
        raise HTTPException(status_code=409, detail=str(exc))
    except GeminiServiceError as exc:
        logger.exception("Gemini Step 3 failed")
        raise HTTPException(status_code=502, detail=f"Gemini API error: {exc}")
    except UpstreamTimeoutError as exc:
        logger.exception("Upstream timeout during Step 3")
        raise HTTPException(status_code=504, detail=f"Upstream timeout: {exc}")
    except Exception:
        logger.exception("/generate failed")
        raise HTTPException(status_code=500, detail="Internal server error")
